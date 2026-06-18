"""
Email OTP verify service.

Drives the shared "confirm an email address" mechanism: send a one-time code via
Auth0 passwordless, then on success link the new Auth0 identity into the caller's
primary user and record the address as a Purrf-confirmed contact.

identity vs contact: an IdP's own ``email_verified`` only means the IdP checked
the address once — it does not prove the mailbox is still reachable. Only an
address confirmed through this flow lands in ``user_emails`` as a usable contact
and notification target; the raw IdP claim stays on ``user_identities`` only.
"""

import os
import re
import time
import uuid

import jwt

from backend.common.constants import is_company_email
from backend.common.environment_constants import EMAIL_OTP_STATE_JWT_SECRET
from backend.common.exceptions import ConflictError
from backend.common.identity_type import IdentityType
from backend.dto.emails_view_dto import (
    EmailEntryDto,
    EmailsViewDto,
    IdentityDto,
)
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity

_STATE_TTL_SECONDS = 600
_STATE_FLOW = "add_email"
_UNLINK_STATE_FLOW = "unlink_identity"
_STATE_ALGORITHM = "HS256"
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_INVALID_STATE_MESSAGE = "Verification state is invalid or expired"
_SET_PRIMARY_STATE_FLOW = "set_primary"


class EmailManagementService:
    def __init__(
        self,
        auth0_client,
        user_emails_repository,
        user_identities_repository,
        logger,
    ):
        """
        Initialize the EmailManagementService with its dependencies.

        Args:
            auth0_client (Auth0Client): Client driving Auth0 passwordless OTP and identity linking.
            user_emails_repository (UserEmailsRepository): Repository handling UserEmailsEntity.
            user_identities_repository (UserIdentitiesRepository): Repository handling UserIdentitiesEntity.
            logger: Application logger.
        """
        self._auth0 = auth0_client
        self._user_emails = user_emails_repository
        self._user_identities = user_identities_repository
        self._state_secret = os.getenv(EMAIL_OTP_STATE_JWT_SECRET)
        self._logger = logger

    async def initiate(
        self, session, current_user_id: int, current_sub: str, email: str
    ) -> dict:
        """Send an OTP and return a signed state JWT binding it to this session."""
        normalized = email.strip().lower()
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email format")
        if await self._user_emails.exists_confirmed_on_other_user(
            session, normalized, current_user_id
        ):
            raise ConflictError("Email already verified by another account")

        self._auth0.start_passwordless(normalized)

        state = self._sign_state(
            _STATE_FLOW,
            user_id=current_user_id,
            sub=current_sub,
            email=normalized,
        )
        return {"state": state}

    async def verify(
        self,
        session,
        current_user_id: int,
        current_sub: str,
        state: str,
        otp: str,
    ) -> dict:
        """
        Confirm the OTP and persist the result.

        The address to verify is taken only from the signed state, never from the
        request, so a tampered email parameter cannot redirect the verification.
        Nothing is written until the OTP and the new identity both check out; the
        Auth0 alias index is synced best-effort after commit so a sync hiccup
        never undoes a confirmed email.
        """
        claims = self._decode_state(state)
        if claims.get("flow") != _STATE_FLOW:
            raise ValueError(_INVALID_STATE_MESSAGE)
        if claims.get("user_id") != current_user_id:
            # CSRF guard: the state must belong to the caller's session.
            raise ValueError(_INVALID_STATE_MESSAGE)
        target_email = claims["email"]

        id_token_claims = self._auth0.exchange_otp(target_email, otp)
        if not id_token_claims.get("email_verified"):
            raise ValueError("Auth0 returned email_verified=false")
        if id_token_claims.get("email", "").lower() != target_email:
            raise ValueError("Verified email does not match the requested address")

        new_sub = id_token_claims["sub"]
        existing_identity = await self._user_identities.get_by_subject_identifier(
            session, new_sub
        )
        if (
            existing_identity is not None
            and existing_identity.user_id != current_user_id
        ):
            raise ConflictError("Identity already linked to another account")

        provider, secondary_user_id = self._split_sub(new_sub)
        self._auth0.link_identity(
            primary_sub=current_sub,
            provider=provider,
            secondary_user_id=secondary_user_id,
        )

        await self._confirm_email(session, current_user_id, target_email)
        if existing_identity is None:
            await self._user_identities.upsert_identity(
                session=session,
                entity=UserIdentitiesEntity(
                    user_id=current_user_id,
                    subject_identifier=new_sub,
                    identity_type=(
                        IdentityType.INTERNAL
                        if is_company_email(target_email)
                        else IdentityType.EXTERNAL
                    ),
                    email_claim=target_email,
                ),
            )
        await session.commit()

        self._sync_alias_best_effort(current_sub, target_email, current_user_id)
        return {"ok": True, "linked_sub": new_sub, "email": target_email}

    async def list_emails_and_identities(
        self, session, current_user_id: int, current_sub: str
    ) -> EmailsViewDto:
        """
        Assemble the comprehensive email/identity view for the Settings page.

        emails[] carry a ``linked_identity_count`` computed in-memory by matching
        each address against the user's identity ``email_claim`` rows
        case-insensitively (no FK, application-layer join). Identities split into
        the ``internal_identities`` list (empty for non-employees; an employee
        may hold more than one, e.g. an SSO login plus an OTP-linked corp email)
        and the ``external_identities`` list. The identity whose subject matches
        ``current_sub`` (the primary the session is bound to) is flagged
        ``is_current_session`` so the UI can badge it and withhold its unlink.

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): user_id of the authenticated caller.
            current_sub (str): JWT ``sub`` of the caller's session (the primary).

        Returns:
            EmailsViewDto: The caller's email rows plus their internal and
            external identities.
        """
        emails = await self._user_emails.list_by_user_id(session, current_user_id)
        identities = await self._user_identities.list_by_user_id(
            session, current_user_id
        )

        # One pass over identities: tally the per-email_claim counts and split
        # the rows into the internal and external identity lists.
        claim_counts: dict[str, int] = {}
        internal_identities: list[IdentityDto] = []
        external_identities: list[IdentityDto] = []
        for identity in identities:
            if identity.email_claim is not None:
                key = identity.email_claim.lower()
                claim_counts[key] = claim_counts.get(key, 0) + 1
            if IdentityType.INTERNAL == identity.identity_type:
                internal_identities.append(self._to_identity_dto(identity, current_sub))
            elif IdentityType.EXTERNAL == identity.identity_type:
                external_identities.append(self._to_identity_dto(identity, current_sub))

        email_views = [
            EmailEntryDto(
                email_id=row.email_id,
                email=row.email,
                otp_confirmed=row.otp_confirmed,
                is_primary=row.is_primary,
                added_at=row.added_at,
                linked_identity_count=claim_counts.get(row.email.lower(), 0),
            )
            for row in emails
        ]

        return EmailsViewDto(
            emails=email_views,
            internal_identities=internal_identities,
            external_identities=external_identities,
        )

    async def _drop_alias_best_effort(
        self, session, user_id: int, primary_sub: str, removed, identities_before
    ) -> None:
        """
        Remove the unlinked identity's address from the Auth0 alias index when
        nothing else references it.

        Skips the drop when another of the user's identities still claims the
        same address (case-insensitive) or it remains a ``user_emails`` contact.
        Best-effort: a failure here is logged and swallowed so it never undoes
        the already-committed unlink.
        """
        email_claim = removed.email_claim
        if not email_claim:
            return
        normalized = email_claim.lower()

        still_linked = any(
            other.identity_id != removed.identity_id
            and (other.email_claim or "").lower() == normalized
            for other in identities_before
        )
        if still_linked:
            return
        if await self._user_emails.get_by_user_and_email(session, user_id, normalized):
            return

        try:
            self._auth0.remove_alias_email_from_primary(primary_sub, email_claim)
        except Exception as exc:
            self._logger.warning(
                "[EmailManagementService] auth.alias_sync.failed user_id=%s op=remove error=%s",
                user_id,
                exc,
            )

    @staticmethod
    def _to_identity_dto(identity, current_sub: str) -> IdentityDto:
        """
        Map a user_identities row to an IdentityDto.

        Args:
            identity (UserIdentitiesEntity): The identity row to map.
            current_sub (str): The session's primary sub; flags the matching row.

        Returns:
            IdentityDto: The mapped identity.
        """
        return IdentityDto(
            identity_id=identity.identity_id,
            subject_identifier=identity.subject_identifier,
            email_claim=identity.email_claim,
            linked_at=identity.linked_at,
            last_used_at=identity.last_login_at,
            is_current_session=identity.subject_identifier == current_sub,
        )

    async def initiate_set_primary(
        self, session, current_user_id: int, email_id: int
    ) -> dict:
        """
        Begin a step-up-OTP switch of the primary contact email.

        Validates the target is promotable, then sends an OTP to the *current*
        primary and snapshots it into the signed state, so :meth:`confirm_set_primary`
        can refuse a swap mid-flow. Sending to the current primary proves the
        caller controls the existing account — defeating the takeover where a
        hijacked session promotes an attacker-added address.

        Returns:
            dict: ``{"state": <jwt>}`` binding the OTP to this switch request.

        Raises:
            ValueError: target missing / not the caller's / not OTP-confirmed,
                or there is no primary to verify against.
            PermissionError: an active employee targeting a non-corp domain.
        """
        target = await self._user_emails.get_by_id(session, email_id)
        await self._validate_promotable(session, current_user_id, target)

        primary = await self._user_emails.get_primary(session, current_user_id)
        if primary is None:
            raise ValueError("No primary email to verify against")

        self._auth0.start_passwordless(primary.email)
        state = self._sign_state(
            _SET_PRIMARY_STATE_FLOW,
            user_id=current_user_id,
            target_email_id=email_id,
            primary_email_at_request=primary.email,
        )
        return {"state": state}

    async def confirm_set_primary(
        self, session, current_user_id: int, email_id: int, state: str, code: str
    ) -> dict:
        """
        Confirm the step-up OTP and swap the primary contact email.

        Validates the signed state, rechecks the primary *before* consuming the
        OTP — refusing if it changed since initiate — verifies the code against
        the primary, re-validates the target is promotable, then swaps the
        primary flag in a single transaction (the partial unique index
        ``user_emails_primary_idx`` keeps at most one primary under races).

        Raises:
            ValueError: invalid/expired/mismatched state, wrong OTP, or the
                target vanished / is not promotable.
            PermissionError: the primary changed since initiate, or an active
                employee targeting a non-corp domain.
        """
        claims = self._decode_state(state)
        if (
            claims.get("flow") != _SET_PRIMARY_STATE_FLOW
            or claims.get("user_id") != current_user_id
            or claims.get("target_email_id") != email_id
        ):
            raise ValueError(_INVALID_STATE_MESSAGE)

        await self._consume_step_up_otp(
            session, current_user_id, claims, code, "switch"
        )

        target = await self._user_emails.get_by_id(session, email_id)
        await self._validate_promotable(session, current_user_id, target)

        await self._user_emails.set_primary(session, current_user_id, email_id)
        await session.commit()
        return {"ok": True}

    async def _validate_promotable(self, session, current_user_id: int, target) -> None:
        """
        Shared guard for promoting ``target`` to primary: it must be the
        caller's, OTP-confirmed, and — for an active employee — a corp address.

        An active employee is ``users.is_active`` True AND holding a
        user_identities row of type INTERNAL; such a user must keep a
        ``circlecat.org`` address as primary so HR / IT can reach them.

        Raises:
            ValueError: missing / owned by another user / not OTP-confirmed.
            PermissionError: an active employee targeting a non-corp domain.
        """
        if target is None or target.user_id != current_user_id:
            raise ValueError("Email not found")
        if not target.otp_confirmed:
            raise ValueError("Email must be verified before promoting to primary")

        # Covers both corp domains (@circlecat.org and @u.circlecat.org); an
        # active employee must keep a company address as primary.
        if not is_company_email(
            target.email
        ) and await self._user_identities.exists_active_internal(
            session, current_user_id
        ):
            raise PermissionError("Active employees must keep a corp email as primary")

    def _sign_state(self, flow: str, **claims) -> str:
        """
        Sign a short-lived state JWT for an OTP flow.

        Stamps the shared envelope — a random ``nonce``, the ``flow`` tag, and
        ``iat``/``exp`` (``_STATE_TTL_SECONDS``) — around the flow-specific
        ``claims``. Companion to :meth:`_decode_state`, which verifies the
        signature and expiry; each caller still checks ``flow`` and its bound
        ids itself.
        """
        now = int(time.time())
        payload = {
            **claims,
            "nonce": uuid.uuid4().hex,
            "flow": flow,
            "iat": now,
            "exp": now + _STATE_TTL_SECONDS,
        }
        return jwt.encode(payload, self._state_secret, algorithm=_STATE_ALGORITHM)

    def _decode_state(self, state: str) -> dict:
        """Decode and verify the state JWT; any JWT error becomes a ValueError."""
        try:
            return jwt.decode(state, self._state_secret, algorithms=[_STATE_ALGORITHM])
        except jwt.PyJWTError:
            raise ValueError(_INVALID_STATE_MESSAGE)

    async def _consume_step_up_otp(
        self, session, current_user_id: int, claims: dict, code: str, operation: str
    ) -> None:
        """
        Verify a step-up OTP against the *current* primary email.

        Shared by the set-primary and unlink confirm paths: re-fetches the
        primary and refuses (``PermissionError``) if it changed since initiate —
        the OTP was mailed to the primary snapshotted in ``claims``, so a swap
        mid-flow must abort rather than accept a code sent to a stale address —
        then consumes the OTP. ``operation`` only customizes the error wording.
        """
        primary = await self._user_emails.get_primary(session, current_user_id)
        if primary is None or primary.email != claims["primary_email_at_request"]:
            raise PermissionError(f"Primary email changed during {operation}; restart")
        self._auth0.exchange_otp(primary.email, code)

    @staticmethod
    def _split_sub(sub: str) -> tuple[str, str]:
        """
        Split an Auth0 ``sub`` (``provider|secondary_user_id``) into the
        ``(provider, secondary_user_id)`` pair the link/unlink calls expect.
        """
        provider, _, secondary_user_id = sub.partition("|")
        return provider, secondary_user_id

    async def _confirm_email(self, session, user_id: int, email: str) -> None:
        """
        Record `email` as an OTP-confirmed contact for the user.

        Flips an existing row to confirmed if present; otherwise inserts one,
        making it primary when the user has no primary yet so they always have a
        notification target.
        """
        existing = await self._user_emails.get_by_user_and_email(
            session, user_id, email
        )
        if existing is not None:
            changed = False
            if not existing.otp_confirmed:
                existing.otp_confirmed = True
                changed = True
            # A migration-backfilled row starts unconfirmed and non-primary;
            # confirming the user's first usable address must also make it
            # primary so they always have a notification target.
            if not existing.is_primary and not await self._user_emails.has_primary(
                session, user_id
            ):
                existing.is_primary = True
                changed = True
            if changed:
                await self._user_emails.upsert_email(session=session, entity=existing)
            return

        # First confirmed address becomes primary so the user has a notification
        # target; later additions stay secondary until explicitly promoted.
        is_primary = not await self._user_emails.has_primary(session, user_id)
        await self._user_emails.upsert_email(
            session=session,
            entity=UserEmailsEntity(
                user_id=user_id,
                email=email,
                otp_confirmed=True,
                is_primary=is_primary,
            ),
        )

    def _sync_alias_best_effort(
        self, primary_sub: str, email: str, user_id: int
    ) -> None:
        """
        Index the confirmed email on the Auth0 primary user, logging on failure.

        Runs after commit: a sync hiccup is logged and swallowed so it never
        undoes an already-confirmed email.
        """
        try:
            self._auth0.add_alias_email_to_primary(primary_sub, email)
        except Exception as exc:
            self._logger.warning(
                "[EmailManagementService] auth.alias_sync.failed user_id=%s op=add error=%s",
                user_id,
                exc,
            )

    async def _validate_unlinkable(
        self, session, current_user_id: int, current_sub: str, identity
    ) -> list:
        """
        Shared guard for unlinking ``identity`` (ownership assumed already
        checked by the caller): refuses the caller's only remaining sign-in, the
        identity backing the current session, and an active employee's INTERNAL
        corp sign-in.

        Re-run at confirm time, not just initiate: between the two steps the user
        may have dropped their other sign-ins or become an active employee, and
        neither must be allowed to strip the last or locked identity.

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): user_id of the authenticated caller.
            current_sub (str): JWT ``sub`` of the caller, the current-session
                identity to protect.
            identity (UserIdentitiesEntity): The identity row to unlink.

        Returns:
            list[UserIdentitiesEntity]: The caller's identities including
            ``identity``, so the caller can reuse them without a second query.

        Raises:
            ConflictError: It is the only identity, or the current session's.
            PermissionError: It is an active employee's INTERNAL identity.
        """
        identities = await self._user_identities.list_by_user(session, current_user_id)
        if len(identities) <= 1:
            raise ConflictError("Cannot remove the only remaining sign-in method")

        if identity.subject_identifier == current_sub:
            raise ConflictError(
                "Cannot remove the sign-in used for the current session; "
                "log in with another method first"
            )

        if (
            IdentityType.INTERNAL == identity.identity_type
            and await self._user_identities.exists_active_internal(
                session, current_user_id
            )
        ):
            raise PermissionError("Active employees cannot remove corp sign-in")

        return identities

    async def initiate_unlink(
        self, session, current_user_id: int, current_sub: str, identity_id: int
    ) -> dict:
        """
        Begin a step-up-OTP unlink of one of the caller's sign-in identities.

        Validates the identity can be unlinked — owned by the caller, not the
        only one, not the current session's, and not an active employee's
        INTERNAL corp sign-in. Because unlinking also drops the identity's
        synced contact email, it additionally refuses when that email is the
        primary (switch the primary first; the primary cannot be deleted). The
        OTP is sent to the current primary, snapshotted into the signed state so
        :meth:`confirm_unlink` can detect a swap mid-flow.

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): user_id of the authenticated caller.
            current_sub (str): JWT ``sub`` of the caller, the current-session
                identity to protect.
            identity_id (int): Primary key of the identity row to unlink.

        Returns:
            dict: ``{"state": <jwt>}`` binding the OTP to this unlink request.

        Raises:
            ValueError: The identity is missing/owned by another user, or there
                is no primary email to verify against.
            ConflictError: It is the only identity, or the current session's.
            PermissionError: It is an active employee's INTERNAL identity, or
                its email is the primary contact.
        """
        identity = await self._user_identities.get_by_id(session, identity_id)
        if identity is None or identity.user_id != current_user_id:
            raise ValueError("Identity not found")

        await self._validate_unlinkable(session, current_user_id, current_sub, identity)

        primary = await self._user_emails.get_primary(session, current_user_id)
        if primary is None:
            raise ValueError("No primary email to verify against")

        if (identity.email_claim or "").lower() == primary.email.lower():
            raise PermissionError(
                "This sign-in's email is your primary contact; "
                "switch your primary email first"
            )

        self._auth0.start_passwordless(primary.email)
        state = self._sign_state(
            _UNLINK_STATE_FLOW,
            user_id=current_user_id,
            target_identity_id=identity_id,
            primary_email_at_request=primary.email,
        )
        return {"state": state}

    async def confirm_unlink(
        self,
        session,
        current_user_id: int,
        current_sub: str,
        identity_id: int,
        state: str,
        code: str,
    ) -> dict:
        """
        Confirm the step-up OTP, unlink the sign-in identity, and drop its
        synced contact email when no other identity still uses that address.

        Validates the signed state (signature, expiry, caller, and that the URL
        ``identity_id`` matches the bound target), rechecks the primary *before*
        consuming the OTP — refusing if it changed since initiate — verifies the
        code against the primary, unlinks from Auth0, deletes the
        ``user_identities`` row, then deletes the matching ``user_emails``
        contact row when no surviving identity claims the same address. The
        Auth0 alias index is reverse-synced best-effort.

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): user_id of the authenticated caller.
            current_sub (str): JWT ``sub`` of the caller, the Auth0 primary user.
            identity_id (int): Primary key from the URL; must match the state.
            state (str): The signed state JWT from initiate.
            code (str): The OTP the user received at the primary address.

        Returns:
            dict: ``{"ok": True}`` once the unlink is committed.

        Raises:
            ValueError: The state is invalid/expired/mismatched, the OTP is
                wrong, or the identity vanished or is owned by another user.
            ConflictError: It became the only identity, or the current session's,
                between initiate and confirm.
            PermissionError: The primary changed since initiate, or it is now an
                active employee's INTERNAL identity.
        """
        claims = self._decode_state(state)
        if claims.get("flow") != _UNLINK_STATE_FLOW:
            raise ValueError(_INVALID_STATE_MESSAGE)
        if claims.get("user_id") != current_user_id:
            raise ValueError(_INVALID_STATE_MESSAGE)
        if claims.get("target_identity_id") != identity_id:
            raise ValueError(_INVALID_STATE_MESSAGE)

        await self._consume_step_up_otp(
            session, current_user_id, claims, code, "unlink"
        )

        identity = await self._user_identities.get_by_id(session, identity_id)
        if identity is None or identity.user_id != current_user_id:
            raise ValueError("Identity not found")

        # Re-check the unlink preconditions against current state — the only/
        # current-session/active-employee guards from initiate may no longer hold.
        identities_before = await self._validate_unlinkable(
            session, current_user_id, current_sub, identity
        )

        provider, secondary_user_id = self._split_sub(identity.subject_identifier)
        self._auth0.unlink_identity(
            primary_sub=current_sub,
            provider=provider,
            secondary_user_id=secondary_user_id,
        )
        await self._user_identities.delete(session, identity_id)

        removed_claim = (identity.email_claim or "").lower()
        still_claimed = any(
            other.identity_id != identity.identity_id
            and (other.email_claim or "").lower() == removed_claim
            for other in identities_before
        )
        if removed_claim and not still_claimed:
            email_row = await self._user_emails.get_by_user_and_email(
                session, current_user_id, removed_claim
            )
            if email_row is not None and not email_row.is_primary:
                await self._user_emails.delete(session, email_row.email_id)

        await session.commit()

        await self._drop_alias_best_effort(
            session, current_user_id, current_sub, identity, identities_before
        )
        return {"ok": True}
