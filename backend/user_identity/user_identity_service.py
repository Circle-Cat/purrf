from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.identity_type import IdentityType
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.permissions import INTERNAL_EMPLOYEE_PERMISSIONS
from backend.dto.user_context_dto import UserContextDto
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.entity.users_entity import UsersEntity


def _iat_as_datetime(last_login_at: int | None) -> datetime | None:
    if last_login_at is None:
        return None
    return datetime.fromtimestamp(last_login_at, tz=timezone.utc)


class UserIdentityService:
    """
    Service responsible for resolving internal user identities from external
    authentication identifiers.

    Resolution is three steps:
      1. sub lookup on user_identities
      2. email fallback: find a migration-backfilled identity by email_claim
         and overwrite its mocked sub in place with the real one
      3. first-login: insert new users + user_identities (+ user_emails if
         sub starts with 'email|')
    """

    def __init__(
        self,
        logger,
        users_repository,
        user_identities_repository,
        user_emails_repository,
        user_permissions_repository,
    ):
        """
        Initialize the UserIdentityService with its dependencies.

        Args:
            logger: Application logger.
            users_repository (UsersRepository): Repository handling UsersEntity.
            user_identities_repository (UserIdentitiesRepository): Repository handling UserIdentitiesEntity.
            user_emails_repository (UserEmailsRepository): Repository handling UserEmailsEntity.
            user_permissions_repository (UserPermissionsRepository): Repository handling UserPermissionsEntity.
        """
        self.logger = logger
        self.users_repository = users_repository
        self.user_identities_repository = user_identities_repository
        self.user_emails_repository = user_emails_repository
        self.user_permissions_repository = user_permissions_repository

    async def find_user_by_sub(
        self,
        session: AsyncSession,
        sub: str,
        last_login_at: int | None = None,
    ) -> UsersEntity | None:
        """
        Step 1: resolve the user by sub.

        A single JOIN fetches the owning user, the identity's id, and the
        stored last_login_at together. The follow-up last_login UPDATE is sent
        only when the token's iat is actually newer than what's stored; within
        a session the CF iat is constant, so the JOIN already holds the latest
        value and the steady-state request stays a single read. On miss,
        returns None without swapping or creating anything.

        Args:
            session (AsyncSession): Active database async session.
            sub (str): Auth0 subject identifier.
            last_login_at (int | None): Auth0 token iat to record as the last
                login; skipped when None or not newer than the stored value.

        Returns:
            UsersEntity | None: The owning user on hit; None on miss.
        """
        found = await self.user_identities_repository.get_user_and_login_state_by_sub(
            session=session, sub=sub
        )
        if found is None:
            return None
        user, identity_id, stored_last_login = found

        login_dt = _iat_as_datetime(last_login_at)
        if login_dt and (stored_last_login is None or stored_last_login < login_dt):
            await self.user_identities_repository.update_last_login(
                session=session, identity_id=identity_id, login_at=login_dt
            )

        return user

    async def email_has_owner(self, session: AsyncSession, email: str) -> bool:
        """
        Whether `email` already belongs to some account — either as an
        OTP-confirmed contact (user_emails) or via the legacy
        users.primary_email column.

        Used by the bootstrap to classify a first-login unique violation: an
        owned email means the login is a second sign-in method for an existing
        account (hold at the verify wall to link, PUR-480), while an unowned
        one means the violation is a real bug and must surface.

        Args:
            session (AsyncSession): Active database async session.
            email (str): Normalized (lowercased) address to check.

        Returns:
            bool: True when some account owns the address.
        """
        if await self.user_emails_repository.get_confirmed_by_email(session, email):
            return True
        return (
            await self.users_repository.get_user_by_primary_email(session, email)
            is not None
        )

    async def create_or_swap_user(
        self,
        session: AsyncSession,
        user_info: UserContextDto,
    ) -> UsersEntity:
        """
        Resolve a user not found by sub lookup.

        Tries step 2 (overwrite a migration-backfilled identity found by
        email) first; on miss, falls through to step 3 (first-login insert).
        Writes the resolved user_id back onto `user_info` (mutates the DTO).

        Args:
            session (AsyncSession): Active database async session.
            user_info (UserContextDto): DTO carrying sub, primary_email,
                identity_type and last_login_at.

        Returns:
            UsersEntity: The linked or newly created user.
        """
        email = user_info.primary_email.lower()
        login_dt = _iat_as_datetime(user_info.last_login_at)

        # Step 2: a deployment migration backfills old users as a user_emails
        # row (otp_confirmed=False) plus a user_identities row carrying a
        # mocked sub. On first real login we find that row by email and
        # overwrite the mocked sub with the real one.
        mocked = await self.user_identities_repository.find_swappable_by_email(
            session=session, email_claim=email
        )
        if mocked:
            user = await self._overwrite_mocked_identity(
                session=session,
                identity=mocked,
                sub=user_info.sub,
                identity_type=user_info.identity_type,
                last_login_at=login_dt,
            )
            user_info.user_id = user.user_id
            return user

        # Step 3: first login.
        user = await self._first_login_insert(
            session=session, user_info=user_info, last_login_at=login_dt
        )
        user_info.user_id = user.user_id
        return user

    async def _overwrite_mocked_identity(
        self,
        session: AsyncSession,
        identity: UserIdentitiesEntity,
        sub: str,
        identity_type: str,
        last_login_at: datetime | None,
    ) -> UsersEntity:
        """
        Overwrite a migration-backfilled identity row (mocked sub) with the
        real Auth0 sub on first real login, in place — keeps the row's user_id
        / linked_at and leaves the migrated user_emails row untouched
        (otp_confirmed stays False; verification is the hard-wall flow, PR5).
        Step 2.
        """
        self.logger.info(
            "[UserIdentityService] overwriting mocked sub %s -> %s for user_id=%s",
            identity.subject_identifier,
            sub,
            identity.user_id,
        )
        identity.subject_identifier = sub
        identity.identity_type = identity_type
        if last_login_at is not None:
            identity.last_login_at = last_login_at
        await self.user_identities_repository.upsert_identity(
            session=session, entity=identity
        )
        return await self.users_repository.get_user_by_user_id(
            session=session, user_id=identity.user_id
        )

    async def _first_login_insert(
        self,
        session: AsyncSession,
        user_info: UserContextDto,
        last_login_at: datetime | None,
    ) -> UsersEntity:
        """
        First-time-login path. Creates the users row, the user_identities row,
        and (for 'email|...' subs only) a primary user_emails row with
        otp_confirmed taken from the token's email_verified claim.

        Google first-login leaves user_emails empty; the user is then sent
        through the hard-wall /verify-required flow (PR5).

        Legacy users.primary_email is still populated for dual-write
        compatibility; it is removed in a later cleanup. users.subject_identifier
        is no longer written — the real sub lives only on the user_identities row.
        """
        sub = user_info.sub
        email = user_info.primary_email.lower()

        new_user = UsersEntity(
            primary_email=email,
            first_name=user_info.first_name or "",
            last_name=user_info.last_name or "",
            preferred_name=None,
            timezone="America/Los_Angeles",
            timezone_updated_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            linkedin_link=None,
            has_mentorship_mentor_experience=None,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

        created_user = await self.users_repository.upsert_users(
            session=session, entity=new_user
        )

        new_identity = UserIdentitiesEntity(
            user_id=created_user.user_id,
            subject_identifier=sub,
            identity_type=user_info.identity_type,
            email_claim=email,
            last_login_at=last_login_at,
        )
        await self.user_identities_repository.upsert_identity(
            session=session, entity=new_identity
        )

        if sub.startswith("email|"):
            # 'email|' is the Auth0 passwordless-email connection: logging in
            # already required entering a one-time code Auth0 mailed to this
            # address, so the mailbox round-trip is done at login. Trusting
            # email_verified here is therefore consistent with the "only an
            # OTP round-trip confirms a contact" doctrine — the passwordless
            # login *is* that round-trip — and lets us seed a confirmed primary
            # without a redundant /verify. (is_primary=True also requires
            # otp_confirmed=True per the user_emails CHECK constraint.)
            new_email_row = UserEmailsEntity(
                user_id=created_user.user_id,
                email=email,
                otp_confirmed=user_info.email_verified,
                is_primary=True,
            )
            await self.user_emails_repository.upsert_email(
                session=session, entity=new_email_row
            )

        # Lifecycle hook: a new internal employee gets the internal
        # permission bundle auto-injected.
        if user_info.identity_type == IdentityType.INTERNAL:
            await self.user_permissions_repository.grant(
                session=session,
                user_id=created_user.user_id,
                permission_names=INTERNAL_EMPLOYEE_PERMISSIONS,
                granted_source="system_internal",
            )

        self.logger.info(
            "[UserIdentityService] first-login: user_id=%s sub=%s identity_type=%s",
            created_user.user_id,
            sub,
            user_info.identity_type,
        )
        return created_user
