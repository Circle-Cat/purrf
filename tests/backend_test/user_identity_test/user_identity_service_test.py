import unittest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from backend.user_identity.user_identity_service import (
    UserIdentityService,
    _iat_as_datetime,
)
from backend.entity.users_entity import UsersEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.dto.user_context_dto import UserContextDto
from backend.common.identity_type import IdentityType
from backend.common.permissions import INTERNAL_EMPLOYEE_PERMISSIONS


class TestUserIdentityService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users_repo = AsyncMock()
        self.identities_repo = AsyncMock()
        self.emails_repo = AsyncMock()
        self.permissions_repo = AsyncMock()
        self.session = AsyncMock()
        self.logger = MagicMock()

        self.service = UserIdentityService(
            logger=self.logger,
            users_repository=self.users_repo,
            user_identities_repository=self.identities_repo,
            user_emails_repository=self.emails_repo,
            user_permissions_repository=self.permissions_repo,
        )

        self.iat = 1_700_000_000
        self.iat_dt = datetime.fromtimestamp(self.iat, tz=timezone.utc)

        self.user = MagicMock(spec=UsersEntity, user_id=10)

        # Default: the login's email is unowned, so first-login creation
        # proceeds. Ownership tests override these explicitly.
        self.emails_repo.exists_claim_by_email.return_value = False
        self.users_repo.get_user_by_primary_email.return_value = None

    # find_user_by_sub — Step 1 sub lookup (single JOIN)
    async def test_find_user_by_sub_hit_without_last_login(self):
        """Sub hit without last_login_at: returns the joined user; update_last_login
        is skipped entirely (no pointless no-op write)."""
        self.identities_repo.get_user_and_login_state_by_sub.return_value = (
            self.user,
            5,
            None,
        )

        result = await self.service.find_user_by_sub(self.session, "sub123")

        self.assertIs(result, self.user)
        self.identities_repo.get_user_and_login_state_by_sub.assert_awaited_once_with(
            session=self.session, sub="sub123"
        )
        self.identities_repo.update_last_login.assert_not_awaited()

    async def test_find_user_by_sub_updates_when_iat_newer(self):
        """Sub hit with a newer iat than stored: update_last_login is called with
        the identity_id returned by the JOIN."""
        self.identities_repo.get_user_and_login_state_by_sub.return_value = (
            self.user,
            5,
            None,
        )

        result = await self.service.find_user_by_sub(
            self.session, "sub123", last_login_at=self.iat
        )

        self.assertIs(result, self.user)
        self.identities_repo.update_last_login.assert_awaited_once_with(
            session=self.session, identity_id=5, login_at=self.iat_dt
        )

    async def test_find_user_by_sub_skips_update_when_iat_not_newer(self):
        """Sub hit but the iat matches the stored last_login (the common in-session
        case): no follow-up UPDATE round-trip is issued."""
        self.identities_repo.get_user_and_login_state_by_sub.return_value = (
            self.user,
            5,
            self.iat_dt,
        )

        result = await self.service.find_user_by_sub(
            self.session, "sub123", last_login_at=self.iat
        )

        self.assertIs(result, self.user)
        self.identities_repo.update_last_login.assert_not_awaited()

    async def test_find_user_by_sub_miss_returns_none(self):
        """Sub miss (JOIN finds no row): returns None, does not swap, create, or
        touch last_login. The INNER JOIN folds the orphaned-identity case into
        this same miss, so there is no separate user-missing branch to test."""
        self.identities_repo.get_user_and_login_state_by_sub.return_value = None

        result = await self.service.find_user_by_sub(
            self.session, "sub_missing", last_login_at=self.iat
        )

        self.assertIsNone(result)
        self.identities_repo.update_last_login.assert_not_awaited()

    # create_or_swap_user — Step 2 swap / Step 3 first-login
    # email_has_owner — needs-link collision classification (PUR-480)
    async def test_email_has_owner_any_contact_claim(self):
        """Any user_emails claim counts, confirmed or not: even an unverified
        backup address must hold a colliding sign-in at the verify wall (which
        then points at verifying it from inside the owning account) instead of
        forking a fresh account."""
        self.emails_repo.exists_claim_by_email.return_value = True

        self.assertTrue(
            await self.service.email_has_owner(self.session, "a@example.com")
        )
        # Short-circuits before the legacy column lookup.
        self.users_repo.get_user_by_primary_email.assert_not_awaited()

    async def test_email_has_owner_legacy_primary_email(self):
        """No contact claim but a legacy users.primary_email owner still
        counts — that column is what the first-login unique violation fires on."""
        self.emails_repo.exists_claim_by_email.return_value = False
        self.users_repo.get_user_by_primary_email.return_value = MagicMock(
            spec=UsersEntity
        )

        self.assertTrue(
            await self.service.email_has_owner(self.session, "a@example.com")
        )

    async def test_email_has_owner_unowned(self):
        """Neither a contact claim nor a legacy owner: not owned."""
        self.emails_repo.exists_claim_by_email.return_value = False
        self.users_repo.get_user_by_primary_email.return_value = None

        self.assertFalse(
            await self.service.email_has_owner(self.session, "a@example.com")
        )

    async def test_create_or_swap_overwrites_mocked_identity_by_email(self):
        """Migration backfill: a user_identities row with a mocked sub is found
        by email; first real login overwrites the mocked sub in place."""
        user_info = UserContextDto(
            sub="google-oauth2|abc",
            primary_email="Alice@Example.com",
            identity_type="external",
            last_login_at=self.iat,
        )
        mocked = MagicMock(
            spec=UserIdentitiesEntity,
            identity_id=7,
            user_id=10,
            subject_identifier="mock|alice@example.com",
        )
        self.identities_repo.find_swappable_by_email.return_value = mocked
        resolved = MagicMock(spec=UsersEntity, user_id=10)
        self.users_repo.get_user_by_user_id.return_value = resolved

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, resolved)
        # looked up by lowercased email
        self.identities_repo.find_swappable_by_email.assert_awaited_once_with(
            session=self.session, email_claim="alice@example.com"
        )
        # mocked sub overwritten in place with the real sub (same row persisted)
        self.assertEqual(mocked.subject_identifier, "google-oauth2|abc")
        self.assertEqual(mocked.identity_type, "external")
        self.assertEqual(mocked.last_login_at, self.iat_dt)
        self.identities_repo.upsert_identity.assert_awaited_once_with(
            session=self.session, entity=mocked
        )
        # resolved by user_id; no new user, no delete, no first-login insert
        self.users_repo.get_user_by_user_id.assert_awaited_once_with(
            session=self.session, user_id=10
        )
        self.users_repo.upsert_users.assert_not_awaited()
        self.assertEqual(user_info.user_id, 10)

    async def test_create_or_swap_overwrite_without_last_login(self):
        """Overwrite with last_login_at None: existing last_login_at untouched."""
        user_info = UserContextDto(
            sub="google-oauth2|abc",
            primary_email="bob@example.com",
            identity_type="external",
            last_login_at=None,
        )
        mocked = MagicMock(
            spec=UserIdentitiesEntity,
            identity_id=8,
            user_id=20,
            subject_identifier="mock|bob@example.com",
            last_login_at=None,
        )
        self.identities_repo.find_swappable_by_email.return_value = mocked
        resolved = MagicMock(spec=UsersEntity, user_id=20)
        self.users_repo.get_user_by_user_id.return_value = resolved

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, resolved)
        self.assertEqual(mocked.subject_identifier, "google-oauth2|abc")
        self.assertIsNone(mocked.last_login_at)
        self.users_repo.upsert_users.assert_not_awaited()
        self.assertEqual(user_info.user_id, 20)

    def _swap_passwordless_user_info(self, email_verified=True, sub="email|xyz"):
        return UserContextDto(
            sub=sub,
            primary_email="Alice@Example.com",
            identity_type="external",
            last_login_at=self.iat,
            email_verified=email_verified,
        )

    def _arrange_swap_hit(self, user_id=10):
        mocked = MagicMock(
            spec=UserIdentitiesEntity,
            identity_id=7,
            user_id=user_id,
            subject_identifier="mock|alice@example.com",
        )
        self.identities_repo.find_swappable_by_email.return_value = mocked
        resolved = MagicMock(spec=UsersEntity, user_id=user_id)
        self.users_repo.get_user_by_user_id.return_value = resolved
        return mocked, resolved

    async def test_create_or_swap_swap_passwordless_confirms_and_promotes(self):
        """Swap hit via passwordless login: the login's OTP round-trip already
        proved the mailbox, so the backfilled claim row is confirmed and, with
        no existing primary, promoted — no redundant verify wall."""
        self._arrange_swap_hit()
        row = MagicMock(spec=UserEmailsEntity, otp_confirmed=False, is_primary=False)
        self.emails_repo.get_by_user_and_email.return_value = row
        self.emails_repo.has_primary.return_value = False

        await self.service.create_or_swap_user(
            self.session, self._swap_passwordless_user_info()
        )

        self.emails_repo.get_by_user_and_email.assert_awaited_once_with(
            session=self.session, user_id=10, email="alice@example.com"
        )
        self.assertTrue(row.otp_confirmed)
        self.assertTrue(row.is_primary)
        self.emails_repo.upsert_email.assert_awaited_once_with(
            session=self.session, entity=row
        )

    async def test_create_or_swap_swap_passwordless_keeps_existing_primary(self):
        """Swap-confirm with a primary already set elsewhere: the claim row is
        confirmed but not promoted (one primary per user)."""
        self._arrange_swap_hit()
        row = MagicMock(spec=UserEmailsEntity, otp_confirmed=False, is_primary=False)
        self.emails_repo.get_by_user_and_email.return_value = row
        self.emails_repo.has_primary.return_value = True

        await self.service.create_or_swap_user(
            self.session, self._swap_passwordless_user_info()
        )

        self.assertTrue(row.otp_confirmed)
        self.assertFalse(row.is_primary)
        self.emails_repo.upsert_email.assert_awaited_once_with(
            session=self.session, entity=row
        )

    async def test_create_or_swap_swap_passwordless_seeds_missing_row(self):
        """Swap-confirm when the backfill left no claim row: a confirmed row is
        seeded (primary when none exists), mirroring first-login behavior."""
        self._arrange_swap_hit()
        self.emails_repo.get_by_user_and_email.return_value = None
        self.emails_repo.has_primary.return_value = False

        await self.service.create_or_swap_user(
            self.session, self._swap_passwordless_user_info()
        )

        self.emails_repo.upsert_email.assert_awaited_once()
        seeded = self.emails_repo.upsert_email.call_args.kwargs["entity"]
        self.assertIsInstance(seeded, UserEmailsEntity)
        self.assertEqual(seeded.user_id, 10)
        self.assertEqual(seeded.email, "alice@example.com")
        self.assertTrue(seeded.otp_confirmed)
        self.assertTrue(seeded.is_primary)

    async def test_create_or_swap_swap_passwordless_already_confirmed_noop(self):
        """Swap-confirm on an already-confirmed primary row: nothing to change,
        no write issued."""
        self._arrange_swap_hit()
        row = MagicMock(spec=UserEmailsEntity, otp_confirmed=True, is_primary=True)
        self.emails_repo.get_by_user_and_email.return_value = row

        await self.service.create_or_swap_user(
            self.session, self._swap_passwordless_user_info()
        )

        self.emails_repo.upsert_email.assert_not_awaited()

    async def test_create_or_swap_swap_passwordless_unverified_claim_untouched(
        self,
    ):
        """Swap via passwordless but token lacks email_verified: no trust, the
        claim row stays untouched and the verify wall applies."""
        self._arrange_swap_hit()

        await self.service.create_or_swap_user(
            self.session, self._swap_passwordless_user_info(email_verified=False)
        )

        self.emails_repo.get_by_user_and_email.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()

    async def test_create_or_swap_swap_google_sub_leaves_email_untouched(self):
        """Swap via a non-passwordless sub: the mailbox was never proved by the
        login, so the claim row stays unconfirmed (hard-wall verify flow)."""
        self._arrange_swap_hit()

        await self.service.create_or_swap_user(
            self.session,
            self._swap_passwordless_user_info(sub="google-oauth2|abc"),
        )

        self.emails_repo.get_by_user_and_email.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()

    async def test_create_or_swap_first_login_email_sub(self):
        """First login with email| sub: creates user, identity AND user_emails.
        email_verified=True (Auth0-verified) -> otp_confirmed True."""
        user_info = UserContextDto(
            sub="email|xyz",
            primary_email="Carol@Example.com",
            identity_type="external",
            last_login_at=self.iat,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=99)
        self.users_repo.upsert_users.return_value = created

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, created)
        self.users_repo.upsert_users.assert_awaited_once()
        # new identity row carries last_login_at
        identity = self.identities_repo.upsert_identity.call_args.kwargs["entity"]
        self.assertEqual(identity.subject_identifier, "email|xyz")
        self.assertEqual(identity.user_id, 99)
        self.assertEqual(identity.last_login_at, self.iat_dt)
        # email| sub -> user_emails write
        self.emails_repo.upsert_email.assert_awaited_once()
        email_row = self.emails_repo.upsert_email.call_args.kwargs["entity"]
        self.assertIsInstance(email_row, UserEmailsEntity)
        self.assertEqual(email_row.email, "carol@example.com")
        self.assertTrue(email_row.otp_confirmed)
        self.assertTrue(email_row.is_primary)
        # non-internal identity: no permission grant
        self.permissions_repo.grant.assert_not_awaited()
        # DTO user_id write-back
        self.assertEqual(user_info.user_id, 99)

    async def test_create_or_swap_first_login_non_email_sub(self):
        """First login with non-email| sub: no user_emails row written."""
        user_info = UserContextDto(
            sub="google-oauth2|abc",
            primary_email="dave@example.com",
            identity_type="external",
            last_login_at=self.iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=77)
        self.users_repo.upsert_users.return_value = created

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, created)
        self.identities_repo.upsert_identity.assert_awaited_once()
        self.emails_repo.upsert_email.assert_not_awaited()
        # non-internal identity: no permission grant
        self.permissions_repo.grant.assert_not_awaited()
        self.assertEqual(user_info.user_id, 77)

    async def test_create_or_swap_owned_claimed_email_returns_none(self):
        """The login's email is already claimed by an existing account —
        confirmed or an unverified backup address; either lives only in
        user_emails, so no unique violation would ever fire: create nothing
        and return None so the bootstrap holds the session at the verify wall
        (PUR-480) instead of creating an orphan account."""
        user_info = UserContextDto(
            sub="google-oauth2|new",
            primary_email="Owned@Example.com",
            identity_type="external",
            last_login_at=self.iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.exists_claim_by_email.return_value = True

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIsNone(result)
        # checked with the lowercased address
        self.emails_repo.exists_claim_by_email.assert_awaited_once_with(
            self.session, "owned@example.com"
        )
        # nothing is created or granted
        self.users_repo.upsert_users.assert_not_awaited()
        self.identities_repo.upsert_identity.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()
        self.permissions_repo.grant.assert_not_awaited()
        self.assertIsNone(user_info.user_id)

    async def test_create_or_swap_owned_legacy_primary_email_returns_none(self):
        """A legacy users.primary_email owner counts too: the proactive check
        classifies the collision before the insert instead of relying on the
        unique-violation round-trip."""
        user_info = UserContextDto(
            sub="email|new",
            primary_email="legacy@example.com",
            identity_type="external",
            last_login_at=self.iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.users_repo.get_user_by_primary_email.return_value = MagicMock(
            spec=UsersEntity
        )

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIsNone(result)
        self.users_repo.upsert_users.assert_not_awaited()
        self.identities_repo.upsert_identity.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()
        self.assertIsNone(user_info.user_id)

    async def test_create_or_swap_swap_wins_over_owned_email_check(self):
        """A swappable migration-backfilled identity is resolved before the
        ownership check: a backfilled user's own first login must swap, not
        stall at the wall."""
        user_info = UserContextDto(
            sub="google-oauth2|abc",
            primary_email="alice@example.com",
            identity_type="external",
            last_login_at=self.iat,
        )
        mocked = MagicMock(
            spec=UserIdentitiesEntity,
            identity_id=7,
            user_id=10,
            subject_identifier="mock|alice@example.com",
        )
        self.identities_repo.find_swappable_by_email.return_value = mocked
        resolved = MagicMock(spec=UsersEntity, user_id=10)
        self.users_repo.get_user_by_user_id.return_value = resolved
        # Even with a (theoretical) claim present, the swap path wins.
        self.emails_repo.exists_claim_by_email.return_value = True

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, resolved)
        self.emails_repo.exists_claim_by_email.assert_not_awaited()

    async def test_create_or_swap_first_login_internal_grants_permissions(self):
        """First login with an internal identity grants the internal employee
        permission bundle via user_permissions_repository.grant."""
        user_info = UserContextDto(
            sub="google-oauth2|emp",
            primary_email="emp@circlecat.org",
            identity_type=IdentityType.INTERNAL,
            last_login_at=self.iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=55)
        self.users_repo.upsert_users.return_value = created

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, created)
        self.permissions_repo.grant.assert_awaited_once_with(
            session=self.session,
            user_id=55,
            permission_names=INTERNAL_EMPLOYEE_PERMISSIONS,
            granted_source="system_internal",
        )
        self.assertEqual(user_info.user_id, 55)

    # _iat_as_datetime helper
    async def test_iat_as_datetime_none(self):
        self.assertIsNone(_iat_as_datetime(None))

    async def test_iat_as_datetime_value(self):
        self.assertEqual(_iat_as_datetime(self.iat), self.iat_dt)


if __name__ == "__main__":
    unittest.main()
