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
      3. first-login: insert new users + user_identities + a user_emails
         claim row (confirmed and primary only for 'email|' subs)
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
        Whether `email` already belongs to some account — as a user_emails
        contact claim, confirmed or an unverified backup address. Every
        account claims its addresses in user_emails (first logins seed one),
        so the table is the single source of ownership.

        Used by the bootstrap to classify a colliding first login: an owned
        email means the login is a second sign-in method for an existing
        account, so the session is held at the verify wall (PUR-480). The
        wall's link only succeeds against an owner that OTP-confirmed the
        address; an unverified claim gets the pointer back to verifying it
        from inside the owning account first.

        Args:
            session (AsyncSession): Active database async session.
            email (str): Normalized (lowercased) address to check.

        Returns:
            bool: True when some account owns the address.
        """
        return await self.user_emails_repository.exists_claim_by_email(session, email)

    async def create_or_swap_user(
        self,
        session: AsyncSession,
        user_info: UserContextDto,
    ) -> UsersEntity | None:
        """
        Resolve a user not found by sub lookup.

        Tries step 2 (overwrite a migration-backfilled identity found by
        email) first; on miss, checks whether the login's email already
        belongs to some account and, only when it does not, falls through to
        step 3 (first-login insert). Writes the resolved user_id back onto
        `user_info` (mutates the DTO).

        Args:
            session (AsyncSession): Active database async session.
            user_info (UserContextDto): DTO carrying sub, primary_email,
                identity_type and last_login_at.

        Returns:
            UsersEntity | None: The linked or newly created user, or None
            when the email already belongs to an existing account — the
            sign-in is a second method for that account, so nothing is
            created and the caller must hold the session at the verify wall
            to link (needs-link, PUR-480).
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
            if user_info.sub.startswith("email|") and user_info.email_verified:
                await self._confirm_swapped_claim_email(
                    session=session, user_id=user.user_id, email=email
                )
            user_info.user_id = user.user_id
            return user

        # The email already belongs to an account as a user_emails claim.
        # The proactive check classifies the collision before the insert:
        # relying on the uq_user_emails_email unique violation alone would
        # first create an orphan users row permanently stuck at the verify
        # wall. Create nothing; the bootstrap marks the session needs_link
        # instead (PUR-480).
        if await self.email_has_owner(session, email):
            self.logger.info(
                "[UserIdentityService] first-login email %s already owned; "
                "holding sub %s for needs-link",
                email,
                user_info.sub,
            )
            return None

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
        / linked_at and does not itself touch the migrated user_emails row.
        For non-passwordless logins otp_confirmed stays False and verification
        is the hard-wall flow (PR5); for passwordless logins the caller runs
        _confirm_swapped_claim_email, since the login already proved the
        mailbox. Step 2.
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

    async def _confirm_swapped_claim_email(
        self,
        session: AsyncSession,
        user_id: int,
        email: str,
    ) -> None:
        """
        Confirm the claim address after a passwordless swap login (step 2).

        A passwordless login is itself the OTP round-trip that proves this
        mailbox — the same doctrine _first_login_insert applies when seeding a
        confirmed primary for 'email|' subs — so a migration-backfilled user
        signing in by email must not be held at the verify wall to repeat it.
        Flips the backfilled user_emails row to otp_confirmed (seeding one if
        the backfill left none) and promotes it to primary when the account
        has no primary yet (the CHECK constraint allows primary only on
        confirmed rows). Already-confirmed rows are left as-is.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The swapped account's user_id.
            email (str): Lowercased claim email of the passwordless login.
        """
        row = await self.user_emails_repository.get_by_user_and_email(
            session=session, user_id=user_id, email=email
        )
        if row is not None and row.otp_confirmed:
            return

        make_primary = not await self.user_emails_repository.has_primary(
            session=session, user_id=user_id
        )
        if row is None:
            row = UserEmailsEntity(
                user_id=user_id,
                email=email,
                otp_confirmed=True,
                is_primary=make_primary,
            )
        else:
            row.otp_confirmed = True
            if make_primary:
                row.is_primary = True
        await self.user_emails_repository.upsert_email(session=session, entity=row)
        self.logger.info(
            "[UserIdentityService] confirmed swapped passwordless claim %s "
            "for user_id=%s (promoted_primary=%s)",
            email,
            user_id,
            make_primary,
        )

    async def _first_login_insert(
        self,
        session: AsyncSession,
        user_info: UserContextDto,
        last_login_at: datetime | None,
    ) -> UsersEntity:
        """
        First-time-login path. Creates the users row, the user_identities row,
        and a user_emails row claiming the login's address, so ownership of the
        address is discoverable from user_emails alone (email_has_owner must
        not depend on the legacy users.primary_email column).

        Only an 'email|...' sub lands the claim confirmed (and therefore
        primary): the passwordless login is itself the mailbox round-trip. Any
        other sub seeds it unconfirmed and non-primary; the user is then sent
        through the hard-wall /verify-required flow (PR5), which confirms the
        row and promotes it to primary.
        """
        sub = user_info.sub
        email = user_info.primary_email.lower()

        new_user = UsersEntity(
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

        # 'email|' is the Auth0 passwordless-email connection: logging in
        # already required entering a one-time code Auth0 mailed to this
        # address, so the mailbox round-trip is done at login. Trusting
        # email_verified here is therefore consistent with the "only an
        # OTP round-trip confirms a contact" doctrine — the passwordless
        # login *is* that round-trip — and lets us seed a confirmed primary
        # without a redundant /verify. Any other sub seeds an unconfirmed,
        # non-primary claim (is_primary=True requires otp_confirmed=True per
        # the user_emails CHECK constraint); the hard-wall verify flow
        # confirms and promotes it later.
        confirmed = sub.startswith("email|") and user_info.email_verified
        new_email_row = UserEmailsEntity(
            user_id=created_user.user_id,
            email=email,
            otp_confirmed=confirmed,
            is_primary=confirmed,
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
