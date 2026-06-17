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
_STATE_ALGORITHM = "HS256"
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_INVALID_STATE_MESSAGE = "Verification state is invalid or expired"


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

        now = int(time.time())
        state = jwt.encode(
            {
                "user_id": current_user_id,
                "sub": current_sub,
                "email": normalized,
                "nonce": uuid.uuid4().hex,
                "flow": _STATE_FLOW,
                "iat": now,
                "exp": now + _STATE_TTL_SECONDS,
            },
            self._state_secret,
            algorithm=_STATE_ALGORITHM,
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

        provider, _, secondary_user_id = new_sub.partition("|")
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
        self, session, current_user_id: int
    ) -> EmailsViewDto:
        """
        Assemble the comprehensive email/identity view for the Settings page.

        emails[] carry a ``linked_identity_count`` computed in-memory by matching
        each address against the user's identity ``email_claim`` rows
        case-insensitively (no FK, application-layer join). Identities split into
        the single ``internal_identity`` (null for non-employees) and the
        ``external_identities`` list.

        Args:
            session (AsyncSession): The active async database session.
            current_user_id (int): user_id of the authenticated caller.

        Returns:
            EmailsViewDto: The caller's email rows plus their internal and
            external identities.
        """
        emails = await self._user_emails.list_by_user_id(session, current_user_id)
        identities = await self._user_identities.list_by_user_id(
            session, current_user_id
        )

        # One pass over identities: tally the per-email_claim counts and split
        # the rows into the single internal identity and the external list.
        claim_counts: dict[str, int] = {}
        internal_identity: IdentityDto | None = None
        external_identities: list[IdentityDto] = []
        for identity in identities:
            if identity.email_claim is not None:
                key = identity.email_claim.lower()
                claim_counts[key] = claim_counts.get(key, 0) + 1
            if IdentityType.INTERNAL == identity.identity_type:
                internal_identity = self._to_identity_dto(identity)
            elif IdentityType.EXTERNAL == identity.identity_type:
                external_identities.append(self._to_identity_dto(identity))

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
            internal_identity=internal_identity,
            external_identities=external_identities,
        )

    @staticmethod
    def _to_identity_dto(identity) -> IdentityDto:
        """
        Map a user_identities row to an IdentityDto.

        Args:
            identity (UserIdentitiesEntity): The identity row to map.

        Returns:
            IdentityDto: The mapped identity.
        """
        return IdentityDto(
            identity_id=identity.identity_id,
            subject_identifier=identity.subject_identifier,
            email_claim=identity.email_claim,
            linked_at=identity.linked_at,
            last_used_at=identity.last_login_at,
        )

    def _decode_state(self, state: str) -> dict:
        """Decode and verify the state JWT; any JWT error becomes a ValueError."""
        try:
            return jwt.decode(state, self._state_secret, algorithms=[_STATE_ALGORITHM])
        except jwt.PyJWTError:
            raise ValueError(_INVALID_STATE_MESSAGE)

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
            if not existing.otp_confirmed:
                existing.otp_confirmed = True
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
