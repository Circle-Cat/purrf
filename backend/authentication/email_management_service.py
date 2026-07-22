"""
Email OTP verify service.

Drives the shared "confirm an email address" mechanism: send a one-time code via
Auth0 passwordless, then on success link the new Auth0 identity into the caller's
account-root user and record the address as a Purrf-confirmed contact.

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
from backend.user_identity.internal_lifecycle import absorb_internal_identity

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
        user_permissions_repository,
        users_repository,
        logger,
    ):
        """
        Initialize the EmailManagementService with its dependencies.

        Args:
            auth0_client (Auth0Client): Client driving Auth0 passwordless OTP and identity linking.
            user_emails_repository (UserEmailsRepository): Repository handling UserEmailsEntity.
            user_identities_repository (UserIdentitiesRepository): Repository handling UserIdentitiesEntity.
            user_permissions_repository (UserPermissionsRepository): Repository
                handling permission grants; used to mirror the internal-employee
                lifecycle hook when a corp sign-in joins an existing account.
            users_repository (UsersRepository): Repository handling UsersEntity;
                used to mirror the internal-employee lifecycle hook when a corp
                sign-in joins an existing account.
            logger: Application logger.
        """
        self._auth0 = auth0_client
        self._user_emails = user_emails_repository
        self._user_identities = user_identities_repository
        self._user_permissions = user_permissions_repository
        self._users = users_repository
        self._state_secret = os.getenv(EMAIL_OTP_STATE_JWT_SECRET)
        self._logger = logger

    async def remove_email(
        self,
        session,
        current_user_id: int,
        current_sub: str,
        current_claim_email: str | None,
        email_id: int,
    ) -> dict:
        """Remove a non-primary address from the caller's account.

        Any non-primary row is removable — a confirmed address is account
        contact data the user owns, and removing it also removes its use as
        a passwordless login identifier (one action, one consequence). Two
        refusals: the primary contact, and — when the caller's session is
        itself a passwordless login — the address that session signed in
        with (deleting it would strand a live token whose next request can
        no longer resolve; same doctrine as the unlink current-session
        guard).

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): user_id of the authenticated caller.
            current_sub (str): JWT ``sub`` of the caller's session; only an
                ``email|`` sub triggers the current-session address guard.
            current_claim_email (str | None): The session token's email
                claim, checked against the target row when ``current_sub``
                is a passwordless login.
            email_id (int): Primary key of the email row to remove.

        Returns:
            dict: ``{"ok": True}`` once the removal is committed.

        Raises:
            ValueError: The row is missing or owned by another user.
            ConflictError: The row is the primary contact, it is the
                address the caller's own passwordless session signed in
                with, or the caller is an active employee removing any
                corp-domain email.
        """
        row = await self._user_emails.get_by_id(session, email_id)
        if row is None or row.user_id != current_user_id:
            raise ValueError("Email not found")
        if row.is_primary:
            raise ConflictError("The primary contact email cannot be removed")
        if (
            current_sub.startswith("email|")
            and current_claim_email
            and row.email == current_claim_email.strip().lower()
        ):
            raise ConflictError(
                "Cannot remove the email used for the current session; "
                "log in with another method first"
            )
        if is_company_email(row.email) and await self._users.exists_active_internal(
            session, current_user_id
        ):
            raise ConflictError(
                "Active employees cannot remove a corp email; "
                "it is their required internal contact"
            )

        await self._user_emails.delete(session, email_id)
        await session.commit()
        return {"ok": True}

    async def initiate(
        self,
        session,
        current_user_id: int,
        current_sub: str,
        email: str,
    ) -> dict:
        """
        Send an OTP and return a signed state JWT binding it to this session.

        The caller adds a contact email to their own account; an address
        claimed by *another* account is refused (confirmed or not —
        addresses are globally exclusive).

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): The caller's user_id.
            current_sub (str): The caller's JWT ``sub``.
            email (str): The address to send the OTP to.

        Returns:
            dict: ``{"state": <signed state JWT>}``.
        """
        normalized = email.strip().lower()
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email format")
        if await self._user_emails.exists_on_other_user(
            session, normalized, current_user_id
        ):
            raise ConflictError(
                "Email already in use by another account. If it's yours, "
                "sign in with a code to that address instead."
            )

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
        Nothing is written until the OTP checks out.

        Only confirms the address as a Purrf contact; it does not create a
        ``user_identities`` row for the OTP's passwordless ``email|`` sub.
        That row would be redundant: since PR1, any OTP-confirmed address
        already works as a passwordless login identifier through routing in
        ``UserIdentityService.create_or_swap_user``, so no separate sign-in
        identity is needed to make it usable. The OTP's Auth0 ``email|`` user
        is left inert — the same as any step-up OTP target — and Auth0 users
        are never merged. The ``existing_identity`` conflict guard is drift
        protection: an ``email|`` identity row can still exist for the
        address from before those rows were retired, and if one does, it
        must already belong to this account. Verifying a company address
        additionally mirrors the internal-employee lifecycle hook — the
        baseline permission bundle is granted and the corp address becomes
        the primary contact.
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
            self._logger.warning(
                "[EmailManagementService] OTP exchange returned email_verified=false"
            )
            raise ValueError("Email verification failed; request a new code")
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

        await self._confirm_email(session, current_user_id, target_email)
        if is_company_email(target_email):
            await self._absorb_internal_identity(session, current_user_id, target_email)
        await session.commit()
        return {"ok": True, "email": target_email}

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
        ``current_sub`` (the account root the session is bound to) is flagged
        ``is_current_session`` so the UI can badge it and withhold its unlink.

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): user_id of the authenticated caller.
            current_sub (str): JWT ``sub`` of the caller's session (the account root).

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
                is_corp=is_company_email(row.email),
                last_login_at=row.last_login_at,
            )
            for row in emails
        ]

        return EmailsViewDto(
            emails=email_views,
            internal_identities=internal_identities,
            external_identities=external_identities,
        )

    @staticmethod
    def _to_identity_dto(identity, current_sub: str) -> IdentityDto:
        """
        Map a user_identities row to an IdentityDto.

        Args:
            identity (UserIdentitiesEntity): The identity row to map.
            current_sub (str): The session's account-root sub; flags the matching row.

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

        An active employee is ``users.is_active`` True AND ``users.is_internal``
        True; such a user must keep a ``circlecat.org`` address as primary so
        HR / IT can reach them.

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
        ) and await self._users.exists_active_internal(session, current_user_id):
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
            raise PermissionError(
                f"Your primary contact email changed during this {operation}; "
                "start over"
            )
        self._auth0.exchange_otp(primary.email, code)

    async def _absorb_internal_identity(
        self, session, user_id: int, email: str
    ) -> None:
        """Delegate to the shared internal-employee lifecycle hook — see
        backend.user_identity.internal_lifecycle.absorb_internal_identity."""
        await absorb_internal_identity(
            session,
            user_id,
            email,
            user_permissions_repository=self._user_permissions,
            user_emails_repository=self._user_emails,
            users_repository=self._users,
            logger=self._logger,
        )

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

    async def _validate_unlinkable(
        self, session, current_user_id: int, current_sub: str, identity
    ) -> None:
        """
        Shared guard for unlinking ``identity`` (ownership assumed already
        checked by the caller): refuses the identity backing the current
        session, and an active employee's INTERNAL corp sign-in.

        A caller's only remaining identity row is not refused: unlinking it
        can never lock the account out. Completing this very step-up OTP
        requires a confirmed primary contact email (``get_primary`` in
        :meth:`initiate_unlink` / :meth:`confirm_unlink`); the primary row is
        undeletable (:meth:`remove_email` refuses it); and a confirmed
        primary is itself a passwordless login path, since any OTP-confirmed
        address already works as a sign-in identifier without a
        ``user_identities`` row (see :meth:`verify`). So the primary always
        outlives the unlink and always logs in — there is no "last sign-in"
        to protect.

        Re-run at confirm time, not just initiate: between the two steps the
        user may have become an active employee, and that must not be allowed
        to strip the locked identity.

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): user_id of the authenticated caller.
            current_sub (str): JWT ``sub`` of the caller, the current-session
                identity to protect.
            identity (UserIdentitiesEntity): The identity row to unlink.

        Raises:
            ConflictError: It is the current session's identity.
            PermissionError: It is an active employee's INTERNAL identity.
        """
        if identity.subject_identifier == current_sub:
            raise ConflictError(
                "Cannot remove the sign-in used for the current session; "
                "log in with another method first"
            )

        if (
            IdentityType.INTERNAL == identity.identity_type
            and await self._users.exists_active_internal(session, current_user_id)
        ):
            raise PermissionError("Active employees cannot remove corp sign-in")

    async def initiate_unlink(
        self, session, current_user_id: int, current_sub: str, identity_id: int
    ) -> dict:
        """
        Begin a step-up-OTP unlink of one of the caller's sign-in identities.

        Validates the identity can be unlinked — owned by the caller, not the
        current session's, and not an active employee's INTERNAL corp
        sign-in. The OTP is sent to the current primary (also the OTP
        target used to prove control of the account), snapshotted into the
        signed state so :meth:`confirm_unlink` can detect a swap mid-flow.

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
            ConflictError: It is the current session's identity.
            PermissionError: It is an active employee's INTERNAL identity.
        """
        identity = await self._user_identities.get_by_id(session, identity_id)
        if identity is None or identity.user_id != current_user_id:
            raise ValueError("Identity not found")

        await self._validate_unlinkable(session, current_user_id, current_sub, identity)

        primary = await self._user_emails.get_primary(session, current_user_id)
        if primary is None:
            raise ValueError("No primary email to verify against")

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
        Confirm the step-up OTP, unlink the sign-in identity, and delete its
        Auth0 user.

        Unlink has a single responsibility: remove the ``user_identities`` row
        for this sign-in method. It never touches ``user_emails`` — email rows
        belong to the account, not to any one identity, and leave only through
        :meth:`remove_email` (or by being the primary, which cannot be
        removed). Validates the signed state (signature, expiry, caller, and
        that the URL ``identity_id`` matches the bound target), rechecks the
        primary *before* consuming the OTP — refusing if it changed since
        initiate — verifies the code against the primary, then deletes the
        ``user_identities`` row. Each sign-in method is its own Auth0 user, so
        the unlinked identity's Auth0 user is deleted too — before the commit,
        so a failed Auth0 delete rolls the whole unlink back rather than
        leaving the two stores disagreeing; on retry the Auth0 delete is
        idempotent (404 counts as done).

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): user_id of the authenticated caller.
            current_sub (str): JWT ``sub`` of the caller, the Auth0 account-root user.
            identity_id (int): Primary key from the URL; must match the state.
            state (str): The signed state JWT from initiate.
            code (str): The OTP the user received at the primary address.

        Returns:
            dict: ``{"ok": True}`` once the unlink is committed.

        Raises:
            ValueError: The state is invalid/expired/mismatched, the OTP is
                wrong, or the identity vanished or is owned by another user.
            ConflictError: It became the current session's identity between
                initiate and confirm.
            PermissionError: The primary changed since initiate, or it is now an
                active employee's INTERNAL identity.
            RateLimitedError: Auth0 throttled the user deletion.
            RuntimeError: The Auth0 user deletion failed; nothing is committed.
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
        await self._validate_unlinkable(session, current_user_id, current_sub, identity)

        await self._user_identities.delete(session, identity_id)

        # The Auth0 user backing this sign-in must not outlive the unlink.
        # Before the commit: if the delete fails the transaction rolls back and
        # the unlink is retryable (delete_user treats 404 as already gone).
        self._auth0.delete_user(identity.subject_identifier)

        await session.commit()
        return {"ok": True}
