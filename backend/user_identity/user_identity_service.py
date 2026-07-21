from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.identity_type import IdentityType, is_rowless_login
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.permissions import INTERNAL_EMPLOYEE_PERMISSIONS
from backend.common.trusted_connections import is_trusted_email_assertion
from backend.dto.user_context_dto import UserContextDto
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.entity.users_entity import UsersEntity
from backend.user_identity.internal_lifecycle import absorb_internal_identity

# A first-login insert must come from a login that just happened: a stale
# token whose address no account holds anymore (e.g. deleted from another
# session) must NOT silently fork a fresh account. Fresh signups reach the
# first request within seconds of the Auth0 login; anything older than this
# re-authenticates instead. 30 minutes absorbs slow onboarding without
# leaving a meaningful fork window.
_MAX_FIRST_LOGIN_TOKEN_AGE_SECONDS = 30 * 60


def _iat_as_datetime(last_login_at: int | None) -> datetime | None:
    if last_login_at is None:
        return None
    return datetime.fromtimestamp(last_login_at, tz=timezone.utc)


class UserIdentityService:
    """
    Service responsible for resolving internal user identities from external
    authentication identifiers.

    Resolution: refuse untrusted, swap, route, refuse stale, first-login —
    every login that creates or enters an account is trusted.
      1. sub lookup on user_identities
      1.5. refuse: any assertion that isn't trusted (see
         backend.common.trusted_connections) is refused outright — no
         account is ever created or entered for it
      2. email fallback: find a migration-backfilled identity by email_claim
         and overwrite its mocked sub in place with the real one
      2.5. trusted-assertion routing: a login whose sub is allowlisted and
         whose address some account has OTP-confirmed resolves to that
         account. A verified 'email|' login is itself the OTP round-trip and
         stays row-less; any other allowlisted (social) sub additionally
         gets its identity row upserted, so the next login resolves at
         step 1.
      2.75. refuse: a first-login insert whose token iat is older than
         _MAX_FIRST_LOGIN_TOKEN_AGE_SECONDS is refused — a stale token must
         not silently fork a fresh account
      3. first-login: insert new users + user_identities + a confirmed,
         primary user_emails claim row (every login reaching this step is
         trusted, by step 1.5's construction)
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

    async def create_or_swap_user(
        self,
        session: AsyncSession,
        user_info: UserContextDto,
    ) -> UsersEntity:
        """
        Resolve a user not found by sub lookup.

        First, refuses outright any login whose assertion is not trusted (see
        backend.common.trusted_connections): no account is created or
        entered, ever — the tenant has only trusted connections, so this is
        the default-deny backstop. Then refuses a first-login insert whose
        token iat is older than `_MAX_FIRST_LOGIN_TOKEN_AGE_SECONDS`: a stale
        token must not silently fork a fresh account for an address no
        account currently holds; this only guards the first-login insert,
        not the swap or routing paths, which resolve into an existing
        account rather than creating one.

        Tries step 2 (overwrite a migration-backfilled identity found by
        email — every assertion reaching here is already trusted, per the
        refusal above) first — an INTERNAL trusted-assertion swap also runs
        the absorb lifecycle hook, same as every other corp-join path; on
        miss, checks step 2.5 (trusted-assertion routing: a login whose sub
        is allowlisted and whose address an account has OTP-confirmed
        returns that account directly — a passwordless login writes nothing,
        a routed social sub additionally gets its identity row upserted, so
        the next login resolves at step 1; an INTERNAL routed login of
        either kind also runs the absorb hook). Otherwise falls through to
        step 3 (first-login insert). Writes the resolved user_id back onto
        `user_info` (mutates the DTO).

        Args:
            session (AsyncSession): Active database async session.
            user_info (UserContextDto): DTO carrying sub, primary_email,
                identity_type and last_login_at.

        Returns:
            UsersEntity: The linked or newly created user — step 2 swap,
            step 2.5 routed owner, or step 3 first-login. Every login
            reaching this method resolves to a user; nothing is refused
            without raising.

        Raises:
            ValueError: The assertion is untrusted (see
                is_trusted_email_assertion), or the token is a stale
                first-login attempt (iat older than
                _MAX_FIRST_LOGIN_TOKEN_AGE_SECONDS) for an address no
                account owns.
        """
        email = user_info.primary_email.lower()
        login_dt = _iat_as_datetime(user_info.last_login_at)

        if not is_trusted_email_assertion(
            user_info.sub, user_info.email_verified, email
        ):
            # No untrusted connection may create or enter an account: seeding
            # would recreate the retired unverified state, and there is no
            # longer a verify wall to hold the session at. The tenant has
            # only trusted connections; this is the default-deny backstop
            # (guard 1).
            raise ValueError("Sign in with a supported method")

        # Step 2: a deployment migration backfills old users as a user_emails
        # row (otp_confirmed=False) plus a user_identities row carrying a
        # mocked sub. On first real login we find that row by email and
        # overwrite the mocked sub with the real one. Swapping IS entering
        # the backfilled account, so it demands the same mailbox proof as
        # routing (step 2.5) — guard 1 above already refused any assertion
        # that isn't trusted, so every lookup here runs on a trusted login.
        mocked = await self.user_identities_repository.find_swappable_by_email(
            session=session, email_claim=email
        )
        if mocked:
            if is_rowless_login(user_info.sub, user_info.identity_type):
                # Row-less external passwordless: the OTP round-trip proves the
                # mailbox, so confirm the backfilled claim and DROP the
                # migration placeholder — no email| row is recorded. Next login
                # resolves by confirmed address (step 2.5).
                await self._confirm_swapped_claim_email(
                    session=session, user_id=mocked.user_id, email=email
                )
                await self.user_identities_repository.delete(
                    session=session, identity_id=mocked.identity_id
                )
                user = await self.users_repository.get_user_by_user_id(
                    session=session, user_id=mocked.user_id
                )
                user_info.user_id = user.user_id
                return user

            user = await self._overwrite_mocked_identity(
                session=session,
                identity=mocked,
                sub=user_info.sub,
                identity_type=user_info.identity_type,
                last_login_at=login_dt,
            )
            # Guard 1 already required a trusted assertion, so the confirm +
            # INTERNAL absorb here always run (no re-check needed).
            await self._confirm_swapped_claim_email(
                session=session, user_id=user.user_id, email=email
            )
            if IdentityType.INTERNAL == user_info.identity_type:
                # A backfilled employee entering via a trusted corp swap
                # gets the full lifecycle (permission bundle + primary
                # promotion), same as every other corp-join path.
                await absorb_internal_identity(
                    session,
                    user.user_id,
                    email,
                    user_permissions_repository=self.user_permissions_repository,
                    user_emails_repository=self.user_emails_repository,
                    logger=self.logger,
                )
            user_info.user_id = user.user_id
            return user

        # Step 2.5 (LinkedIn-style routing): a trusted assertion — a verified
        # passwordless login (itself a first-party OTP round-trip) or a
        # verified login from an allowlisted social IdP — for an address some
        # account has OTP-confirmed logs straight into that account. Guard 1
        # above already refused any assertion that isn't trusted, so every
        # login reaching here qualifies. Passwordless writes nothing
        # (row-less, idempotent re-resolution); a routed social sub
        # additionally gets its identity row upserted below, so the next
        # login resolves at step 1.
        confirmed = await self.user_emails_repository.get_confirmed_by_email(
            session=session, email=email
        )
        if confirmed is not None:
            user = await self.users_repository.get_user_by_user_id(
                session=session, user_id=confirmed.user_id
            )
            if not user_info.sub.startswith("email|"):
                # Social credentials stay sub-routed: record the identity
                # so the next login resolves at step 1. Passwordless stays
                # row-less — the verified address itself is the identifier.
                # A concurrent duplicate insert trips the subject_identifier
                # UNIQUE constraint; the middleware's SAVEPOINT + re-find
                # already handles that race.
                await self.user_identities_repository.upsert_identity(
                    session=session,
                    entity=UserIdentitiesEntity(
                        user_id=user.user_id,
                        subject_identifier=user_info.sub,
                        identity_type=user_info.identity_type,
                        email_claim=email,
                        last_login_at=login_dt,
                    ),
                )
            if IdentityType.INTERNAL == user_info.identity_type:
                # An employee's corp sign-in joining an existing account
                # mirrors the first-login lifecycle hook. Runs for ANY
                # routed login, not just social: absorb is idempotent
                # (diffed grants, promotion guarded), so per-request
                # re-routing of row-less passwordless subs is safe.
                await absorb_internal_identity(
                    session,
                    user.user_id,
                    email,
                    user_permissions_repository=self.user_permissions_repository,
                    user_emails_repository=self.user_emails_repository,
                    logger=self.logger,
                )
            user_info.user_id = user.user_id
            self.logger.info(
                "[UserIdentityService] trusted-assertion login routed to "
                "user_id=%s by confirmed address (sub=%s)",
                user.user_id,
                user_info.sub,
            )
            return user

        # Step 3: first login. Guard 1 already refused any assertion that
        # isn't trusted, so no unowned-collision check is needed here — an
        # address with a confirmed owner would already have routed above,
        # and post-migration every user_emails row is confirmed, so there is
        # no unconfirmed claim left to collide with.
        if login_dt is not None and (datetime.now(timezone.utc) - login_dt) > timedelta(
            seconds=_MAX_FIRST_LOGIN_TOKEN_AGE_SECONDS
        ):
            raise ValueError("Session expired; sign in again")
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
        Every swap is trust-gated (only trusted assertions, verified logins,
        or allowlisted IdPs reach this point); the caller always runs
        _confirm_swapped_claim_email to mark the swapped email as confirmed,
        since the login already proved mailbox ownership. Step 2.
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
        Confirm the claim address after a trusted-assertion swap login (step 2).

        A trusted assertion — a passwordless login's own OTP round-trip, or a
        verified login from an allowlisted social IdP — proves this mailbox,
        the same doctrine _first_login_insert applies when seeding a
        confirmed primary — so a migration-backfilled user signing in this
        way must not be held at the verify wall to repeat the proof.
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
            "[UserIdentityService] confirmed swapped trusted-assertion claim %s "
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
        and a user_emails row claiming the login's address, so ownership of
        the address is discoverable from user_emails alone (not the legacy
        users.primary_email column).

        create_or_swap_user's guard 1 refuses any untrusted assertion before
        this method is ever reached, so every claim seeded here is confirmed
        and primary by construction — the login itself is the mailbox proof
        (a passwordless round-trip, or a verified assertion from an
        allowlisted social IdP).
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

        # Row-less external passwordless leaves no user_identities row — the
        # confirmed user_emails row seeded below is its sole anchor. google /
        # INTERNAL (incl. corp passwordless) still record a sub-routed row.
        if not is_rowless_login(sub, user_info.identity_type):
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

        # Every login reaching this insert is a trusted assertion (guard 1 in
        # create_or_swap_user refuses anything else before this method runs):
        # an allowlisted IdP reporting the address verified, or the
        # passwordless login's own OTP round-trip. 'email|' is the Auth0
        # passwordless-email connection: logging in already required entering
        # a one-time code Auth0 mailed to this address, so the mailbox
        # round-trip is done at login. 'google-oauth2|' is Google, the
        # mailbox authority for its verified addresses. The claim is
        # therefore always seeded confirmed and primary.
        new_email_row = UserEmailsEntity(
            user_id=created_user.user_id,
            email=email,
            otp_confirmed=True,
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
