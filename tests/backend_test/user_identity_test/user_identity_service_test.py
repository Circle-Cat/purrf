import time
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
        # A "just happened" iat, for tests that must clear the first-login
        # staleness guard (self.iat above is a fixed, long-past timestamp
        # used only for last_login_at bookkeeping assertions on swap/routing
        # paths, which the staleness guard does not touch).
        self.fresh_iat = int(time.time())
        self.fresh_iat_dt = datetime.fromtimestamp(self.fresh_iat, tz=timezone.utc)

        self.user = MagicMock(spec=UsersEntity, user_id=10)

        # Default: no confirmed owner found for the email address (routing
        # doesn't apply). Email-routing tests override this explicitly.
        self.emails_repo.get_confirmed_by_email.return_value = None

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
    async def test_create_or_swap_overwrites_mocked_identity_by_email(self):
        """Migration backfill: a user_identities row with a mocked sub is found
        by email; first real login overwrites the mocked sub in place."""
        user_info = UserContextDto(
            sub="google-oauth2|abc",
            primary_email="Alice@Example.com",
            identity_type="external",
            last_login_at=self.iat,
            email_verified=True,
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
        # already-confirmed row: the trusted swap's confirm step is a no-op here
        self.emails_repo.get_by_user_and_email.return_value = MagicMock(
            spec=UserEmailsEntity, otp_confirmed=True
        )

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
            email_verified=True,
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
        # already-confirmed row: the trusted swap's confirm step is a no-op here
        self.emails_repo.get_by_user_and_email.return_value = MagicMock(
            spec=UserEmailsEntity, otp_confirmed=True
        )

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

    async def test_create_or_swap_swap_google_sub_confirms_email(self):
        """Swap via a trusted Google sub: the allowlisted IdP's verified
        assertion is first-party mailbox proof too, so the swap-confirm site
        fires just like a passwordless swap — no redundant verify wall."""
        self._arrange_swap_hit()
        row = MagicMock(spec=UserEmailsEntity, otp_confirmed=False, is_primary=False)
        self.emails_repo.get_by_user_and_email.return_value = row
        self.emails_repo.has_primary.return_value = False

        await self.service.create_or_swap_user(
            self.session,
            self._swap_passwordless_user_info(sub="google-oauth2|abc"),
        )

        self.emails_repo.get_by_user_and_email.assert_awaited_once_with(
            session=self.session, user_id=10, email="alice@example.com"
        )
        self.assertTrue(row.otp_confirmed)
        self.assertTrue(row.is_primary)

    async def test_create_or_swap_swap_google_internal_absorbs_lifecycle(self):
        """A trusted Google swap for an INTERNAL identity also runs the
        absorb hook (permission bundle grant), same as every other
        corp-join path."""
        self._arrange_swap_hit()
        row = MagicMock(spec=UserEmailsEntity, otp_confirmed=False, is_primary=False)
        self.emails_repo.get_by_user_and_email.return_value = row
        self.emails_repo.has_primary.return_value = False
        self.permissions_repo.get_active_permission_names.return_value = []

        user_info = UserContextDto(
            sub="google-oauth2|abc",
            primary_email="Alice@Example.com",
            identity_type=IdentityType.INTERNAL,
            last_login_at=self.iat,
            email_verified=True,
        )

        await self.service.create_or_swap_user(self.session, user_info)

        self.permissions_repo.grant.assert_awaited_once()

    async def test_swap_external_passwordless_confirms_and_deletes_placeholder(self):
        """External passwordless swap is row-less: confirm the migrated claim
        and DELETE the manual| placeholder — never overwrite it into an email|
        row."""
        mocked, resolved = self._arrange_swap_hit()
        row = MagicMock(spec=UserEmailsEntity, otp_confirmed=False, is_primary=False)
        self.emails_repo.get_by_user_and_email.return_value = row
        self.emails_repo.has_primary.return_value = False

        result = await self.service.create_or_swap_user(
            self.session, self._swap_passwordless_user_info()  # email|xyz, external
        )

        self.assertIs(result, resolved)
        # confirmed…
        self.assertTrue(row.otp_confirmed)
        self.emails_repo.upsert_email.assert_awaited_once_with(
            session=self.session, entity=row
        )
        # …placeholder deleted, NO overwrite (no email| row ever written).
        self.identities_repo.delete.assert_awaited_once_with(
            session=self.session, identity_id=7
        )
        self.identities_repo.upsert_identity.assert_not_awaited()

    async def test_swap_google_still_overwrites_and_keeps_row(self):
        """Google swap is NOT row-less: overwrite the placeholder with the real
        sub (row kept), and never delete it — regression guard."""
        mocked, resolved = self._arrange_swap_hit()
        row = MagicMock(spec=UserEmailsEntity, otp_confirmed=False, is_primary=False)
        self.emails_repo.get_by_user_and_email.return_value = row
        self.emails_repo.has_primary.return_value = False

        await self.service.create_or_swap_user(
            self.session,
            self._swap_passwordless_user_info(sub="google-oauth2|abc"),
        )

        self.identities_repo.upsert_identity.assert_awaited()
        self.identities_repo.delete.assert_not_awaited()

    async def test_create_or_swap_untrusted_sub_never_swaps(self):
        """The backfill swap is trust-gated: an unlisted connection's email
        claim must not swap into (and thereby enter) a backfilled account.
        Post stale-token-guard (PUR-505), the untrusted-assertion refusal at
        the top of the method fires first — no repo call is ever made,
        including the swap lookup itself."""
        user_info = UserContextDto(
            sub="auth0|123",
            primary_email="legacy@b.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
        )
        mocked = MagicMock(
            spec=UserIdentitiesEntity, user_id=10, subject_identifier="manual|x"
        )
        self.identities_repo.find_swappable_by_email.return_value = mocked

        with self.assertRaisesRegex(ValueError, "Sign in with a supported method"):
            await self.service.create_or_swap_user(self.session, user_info)

        self.identities_repo.find_swappable_by_email.assert_not_awaited()
        self.identities_repo.upsert_identity.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()

    async def test_create_or_swap_unverified_sub_never_swaps(self):
        """An unverified login must not swap either — the claim proves
        nothing. Post stale-token-guard (PUR-505), the untrusted-assertion
        refusal fires before any repo call."""
        user_info = UserContextDto(
            sub="email|x",
            primary_email="legacy@b.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=False,
        )
        mocked = MagicMock(
            spec=UserIdentitiesEntity, user_id=10, subject_identifier="manual|x"
        )
        self.identities_repo.find_swappable_by_email.return_value = mocked

        with self.assertRaisesRegex(ValueError, "Sign in with a supported method"):
            await self.service.create_or_swap_user(self.session, user_info)

        self.identities_repo.find_swappable_by_email.assert_not_awaited()
        self.identities_repo.upsert_identity.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()

    async def test_create_or_swap_first_login_email_sub(self):
        """External passwordless first login is ROW-LESS: creates user +
        confirmed user_emails, but writes NO user_identities row."""
        user_info = UserContextDto(
            sub="email|xyz",
            primary_email="Carol@Example.com",
            identity_type="external",
            last_login_at=self.fresh_iat,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=99)
        self.users_repo.upsert_users.return_value = created

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, created)
        self.users_repo.upsert_users.assert_awaited_once()
        # ROW-LESS: no identity row written.
        self.identities_repo.upsert_identity.assert_not_awaited()
        # confirmed primary user_emails row still seeded.
        self.emails_repo.upsert_email.assert_awaited_once()
        email_row = self.emails_repo.upsert_email.call_args.kwargs["entity"]
        self.assertEqual(email_row.email, "carol@example.com")
        self.assertTrue(email_row.otp_confirmed)
        self.assertTrue(email_row.is_primary)
        self.permissions_repo.grant.assert_not_awaited()
        self.assertEqual(user_info.user_id, 99)

    async def test_create_or_swap_first_login_internal_email_sub_writes_identity(self):
        """Corp (INTERNAL) passwordless first login is NOT row-less: it still
        records the identity row so the user is classified internal."""
        user_info = UserContextDto(
            sub="email|xyz",
            primary_email="dev@circlecat.org",
            identity_type=IdentityType.INTERNAL,
            last_login_at=self.fresh_iat,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=42)
        self.users_repo.upsert_users.return_value = created

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, created)
        self.identities_repo.upsert_identity.assert_awaited_once()
        identity = self.identities_repo.upsert_identity.call_args.kwargs["entity"]
        self.assertEqual(identity.subject_identifier, "email|xyz")
        self.assertEqual(identity.user_id, 42)
        # INTERNAL first-login grants the employee bundle.
        self.permissions_repo.grant.assert_awaited_once()

    async def test_create_or_swap_first_login_non_email_sub_untrusted_raises(
        self,
    ):
        """First login with a non-email| (google) sub and no email_verified
        assertion: email_verified defaults to False, so the IdP's claim is
        untrusted. Post stale-token-guard (PUR-505) this refuses outright —
        seeding an unconfirmed claim for an untrusted login would recreate
        the retired unverified state, and no account is created or entered.
        (Previously this seeded an unconfirmed, non-primary claim row sent
        through the hard-wall verify flow; that flow no longer exists.)"""
        user_info = UserContextDto(
            sub="google-oauth2|abc",
            primary_email="Dave@Example.com",
            identity_type="external",
            last_login_at=self.iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None

        with self.assertRaisesRegex(ValueError, "Sign in with a supported method"):
            await self.service.create_or_swap_user(self.session, user_info)

        self.users_repo.upsert_users.assert_not_awaited()
        self.identities_repo.upsert_identity.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()
        self.permissions_repo.grant.assert_not_awaited()
        self.assertIsNone(user_info.user_id)

    async def test_create_or_swap_first_login_email_sub_unverified_raises(
        self,
    ):
        """First login with an email| sub whose token says email_verified=False
        is untrusted (the OTP round-trip proves nothing without it). Post
        stale-token-guard (PUR-505) this refuses outright with no account
        creation. (Previously this seeded an unconfirmed, non-primary claim
        row; that transitional state is retired.)"""
        user_info = UserContextDto(
            sub="email|xyz",
            primary_email="carol@example.com",
            identity_type="external",
            last_login_at=self.iat,
            email_verified=False,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=99)
        self.users_repo.upsert_users.return_value = created

        with self.assertRaisesRegex(ValueError, "Sign in with a supported method"):
            await self.service.create_or_swap_user(self.session, user_info)

        self.emails_repo.upsert_email.assert_not_awaited()

    async def test_create_or_swap_owned_claimed_email_untrusted_raises(self):
        """The login's email is already claimed by an existing account, but
        the assertion itself is untrusted (email_verified defaults False for
        this google sub). Post stale-token-guard (PUR-505) the
        untrusted-assertion refusal fires before anything else runs: create
        nothing, grant nothing."""
        user_info = UserContextDto(
            sub="google-oauth2|new",
            primary_email="Owned@Example.com",
            identity_type="external",
            last_login_at=self.iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None

        with self.assertRaisesRegex(ValueError, "Sign in with a supported method"):
            await self.service.create_or_swap_user(self.session, user_info)

        # nothing is created or granted
        self.users_repo.upsert_users.assert_not_awaited()
        self.identities_repo.upsert_identity.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()
        self.permissions_repo.grant.assert_not_awaited()
        self.assertIsNone(user_info.user_id)

    async def test_create_or_swap_swap_wins_over_owned_email_check(self):
        """A swappable migration-backfilled identity is resolved before
        anything else runs: a backfilled user's own first login must swap,
        not fall through to routing or first-login."""
        user_info = UserContextDto(
            sub="google-oauth2|abc",
            primary_email="alice@example.com",
            identity_type="external",
            last_login_at=self.iat,
            email_verified=True,
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
        # already-confirmed row: the trusted swap's confirm step is a no-op here
        self.emails_repo.get_by_user_and_email.return_value = MagicMock(
            spec=UserEmailsEntity, otp_confirmed=True
        )

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, resolved)
        self.emails_repo.get_confirmed_by_email.assert_not_awaited()

    async def test_create_or_swap_first_login_internal_grants_permissions(self):
        """First login with an internal identity grants the internal employee
        permission bundle via user_permissions_repository.grant. Uses a
        trusted (verified) assertion and a fresh iat so neither the
        untrusted-assertion refusal nor the first-login staleness guard
        (PUR-505) fires — this test targets the permission-grant side
        effect, not trust or staleness."""
        user_info = UserContextDto(
            sub="google-oauth2|emp",
            primary_email="emp@circlecat.org",
            identity_type=IdentityType.INTERNAL,
            last_login_at=self.fresh_iat,
            email_verified=True,
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

    async def test_create_or_swap_first_login_google_seeds_confirmed_primary(self):
        """A trusted first login seeds its address confirmed AND primary —
        the verify wall no longer exists for allowlisted IdPs."""
        user_info = UserContextDto(
            sub="google-oauth2|new",
            primary_email="new@gmail.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=77)
        self.users_repo.upsert_users.return_value = created

        await self.service.create_or_swap_user(self.session, user_info)

        seeded = self.emails_repo.upsert_email.await_args.kwargs["entity"]
        self.assertTrue(seeded.otp_confirmed)
        self.assertTrue(seeded.is_primary)

    # create_or_swap_user — Step 2.5 passwordless email-routing (LinkedIn-style)
    async def test_create_or_swap_routes_passwordless_to_confirmed_owner(self):
        """A verified 'email|' login whose address some account already
        OTP-confirmed resolves straight to that account: no swap, no insert,
        no needs-link hold — the passwordless login is itself the OTP."""
        user_info = UserContextDto(
            sub="email|otp1",
            primary_email="Owner@Example.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = MagicMock(
            spec=UserEmailsEntity, user_id=10, otp_confirmed=True
        )
        self.users_repo.get_user_by_user_id.return_value = self.user

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, self.user)
        self.assertEqual(user_info.user_id, 10)
        self.emails_repo.get_confirmed_by_email.assert_awaited_once_with(
            session=self.session, email="owner@example.com"
        )
        # Pure resolution: nothing is created or modified.
        self.identities_repo.upsert_identity.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()
        self.users_repo.upsert_users.assert_not_awaited()

    async def test_create_or_swap_unverified_passwordless_never_routes(self):
        """email_verified=False is untrusted; post stale-token-guard
        (PUR-505) the untrusted-assertion refusal fires before routing (or
        anything else) is even consulted."""
        user_info = UserContextDto(
            sub="email|otp1",
            primary_email="a@b.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=False,
        )
        self.identities_repo.find_swappable_by_email.return_value = None

        with self.assertRaisesRegex(ValueError, "Sign in with a supported method"):
            await self.service.create_or_swap_user(self.session, user_info)

        self.emails_repo.get_confirmed_by_email.assert_not_awaited()

    async def test_create_or_swap_routes_trusted_google_and_links_sub(self):
        """A verified Google login whose address some account OTP-confirmed
        routes into that account AND records the identity row, so the next
        login resolves at step 1 (social credentials stay sub-routed)."""
        user_info = UserContextDto(
            sub="google-oauth2|123",
            primary_email="Owner@Example.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
            last_login_at=self.iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = MagicMock(
            spec=UserEmailsEntity, user_id=10, otp_confirmed=True
        )
        self.users_repo.get_user_by_user_id.return_value = self.user

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, self.user)
        self.assertEqual(user_info.user_id, 10)
        self.identities_repo.upsert_identity.assert_awaited_once()
        linked = self.identities_repo.upsert_identity.await_args.kwargs["entity"]
        self.assertEqual(linked.user_id, 10)
        self.assertEqual(linked.subject_identifier, "google-oauth2|123")
        self.assertEqual(linked.email_claim, "owner@example.com")
        self.assertEqual(linked.identity_type, IdentityType.EXTERNAL)
        # Routing links the credential but never creates users or email rows.
        self.users_repo.upsert_users.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()
        # EXTERNAL routed logins never absorb the internal lifecycle.
        self.permissions_repo.grant.assert_not_awaited()

    async def test_create_or_swap_routed_internal_mirrors_employee_lifecycle(self):
        """An employee's corp sign-in routing into an existing account gets
        the diffed permission bundle and the corp address promoted to
        primary — same as the bridge's absorb hook."""
        user_info = UserContextDto(
            sub="google-oauth2|corp",
            primary_email="emp@circlecat.org",
            identity_type=IdentityType.INTERNAL,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = MagicMock(
            spec=UserEmailsEntity, user_id=10, otp_confirmed=True
        )
        self.users_repo.get_user_by_user_id.return_value = self.user
        self.permissions_repo.get_active_permission_names.return_value = []
        self.emails_repo.get_by_user_and_email.return_value = MagicMock(
            spec=UserEmailsEntity, email_id=7, otp_confirmed=True, is_primary=False
        )

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, self.user)
        self.permissions_repo.grant.assert_awaited_once()
        self.emails_repo.set_primary.assert_awaited_once_with(self.session, 10, 7)

    async def test_create_or_swap_routed_passwordless_stays_rowless(self):
        """email| routing must NOT write an identity row — the verified
        address itself is the identifier (end-state model)."""
        user_info = UserContextDto(
            sub="email|otp1",
            primary_email="owner@example.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = MagicMock(
            spec=UserEmailsEntity, user_id=10, otp_confirmed=True
        )
        self.users_repo.get_user_by_user_id.return_value = self.user

        await self.service.create_or_swap_user(self.session, user_info)

        self.identities_repo.upsert_identity.assert_not_awaited()

    async def test_create_or_swap_routed_passwordless_internal_absorbs_lifecycle(
        self,
    ):
        """A routed passwordless (email|) INTERNAL login also runs the
        absorb hook — INTERNAL absorb applies to ANY routed login, not just
        social — while staying row-less (no identity upsert)."""
        user_info = UserContextDto(
            sub="email|x",
            primary_email="emp@circlecat.org",
            identity_type=IdentityType.INTERNAL,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = MagicMock(
            spec=UserEmailsEntity, user_id=10, otp_confirmed=True
        )
        self.users_repo.get_user_by_user_id.return_value = self.user
        self.permissions_repo.get_active_permission_names.return_value = []
        self.emails_repo.get_by_user_and_email.return_value = MagicMock(
            spec=UserEmailsEntity, email_id=7, otp_confirmed=True, is_primary=False
        )

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, self.user)
        self.permissions_repo.grant.assert_awaited_once()
        self.identities_repo.upsert_identity.assert_not_awaited()

    async def test_create_or_swap_untrusted_sub_never_email_routes(self):
        """An unlisted connection (auth0 database) with a verified claim is
        default-denied. Post stale-token-guard (PUR-505) this raises before
        routing (or anything else) is consulted."""
        user_info = UserContextDto(
            sub="auth0|123",
            primary_email="a@b.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None

        with self.assertRaisesRegex(ValueError, "Sign in with a supported method"):
            await self.service.create_or_swap_user(self.session, user_info)

        self.emails_repo.get_confirmed_by_email.assert_not_awaited()

    async def test_create_or_swap_swap_still_wins_over_email_routing(self):
        """A migration-backfilled (mocked-sub) identity is resolved before
        email-routing is consulted: the row-less passwordless swap confirms
        the claim and deletes the placeholder, which routing alone would
        never do."""
        user_info = UserContextDto(
            sub="email|otp1",
            primary_email="legacy@b.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
            last_login_at=self.iat,
        )
        mocked = MagicMock(
            spec=UserIdentitiesEntity,
            identity_id=9,
            user_id=10,
            subject_identifier="mock|legacy",
        )
        self.identities_repo.find_swappable_by_email.return_value = mocked
        self.users_repo.get_user_by_user_id.return_value = self.user
        self.emails_repo.get_by_user_and_email.return_value = MagicMock(
            spec=UserEmailsEntity, otp_confirmed=True
        )

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, self.user)
        self.identities_repo.delete.assert_awaited_once_with(
            session=self.session, identity_id=9
        )
        self.identities_repo.upsert_identity.assert_not_awaited()
        self.emails_repo.get_confirmed_by_email.assert_not_awaited()

    async def test_create_or_swap_passwordless_unowned_falls_to_first_login(self):
        """No confirmed row and no claim at all: first-login creation runs
        exactly as before (routing is consulted but misses)."""
        user_info = UserContextDto(
            sub="email|otp1",
            primary_email="new@b.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=77)
        self.users_repo.upsert_users.return_value = created

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, created)
        self.assertEqual(user_info.user_id, 77)
        self.emails_repo.get_confirmed_by_email.assert_awaited_once()

    # create_or_swap_user — PUR-505 stale-token guard + untrusted refusal
    async def test_create_or_swap_untrusted_sub_raises_before_any_repo_call(self):
        """An untrusted connection is refused at the very top of the method:
        no swap lookup, no routing lookup, no ownership check — the tenant
        has only trusted connections, so this is the default-deny backstop
        and nothing is ever awaited on the repositories."""
        user_info = UserContextDto(
            sub="auth0|123",
            primary_email="legacy@b.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
        )

        with self.assertRaisesRegex(ValueError, "Sign in with a supported method"):
            await self.service.create_or_swap_user(self.session, user_info)

        self.identities_repo.find_swappable_by_email.assert_not_awaited()
        self.emails_repo.get_confirmed_by_email.assert_not_awaited()

    async def test_create_or_swap_unverified_trusted_prefix_sub_raises(self):
        """A trusted-prefix sub (email|) whose token says email_verified=False
        is still untrusted — the round-trip proves nothing without it — and
        is refused the same as an unlisted connection, before any repo
        call."""
        user_info = UserContextDto(
            sub="email|x",
            primary_email="legacy@b.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=False,
        )

        with self.assertRaisesRegex(ValueError, "Sign in with a supported method"):
            await self.service.create_or_swap_user(self.session, user_info)

        self.identities_repo.find_swappable_by_email.assert_not_awaited()
        self.emails_repo.get_confirmed_by_email.assert_not_awaited()

    async def test_create_or_swap_stale_trusted_token_unowned_raises_session_expired(
        self,
    ):
        """A stale trusted token (iat older than
        _MAX_FIRST_LOGIN_TOKEN_AGE_SECONDS) for an address no account owns
        must not silently fork a fresh account: the first-login insert is
        refused so the client re-authenticates instead."""
        stale_iat = int(time.time()) - 3600
        user_info = UserContextDto(
            sub="email|xyz",
            primary_email="new@example.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
            last_login_at=stale_iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = None

        with self.assertRaisesRegex(ValueError, "Session expired; sign in again"):
            await self.service.create_or_swap_user(self.session, user_info)

        self.users_repo.upsert_users.assert_not_awaited()
        self.identities_repo.upsert_identity.assert_not_awaited()
        self.emails_repo.upsert_email.assert_not_awaited()

    async def test_create_or_swap_fresh_trusted_token_still_first_login_inserts(
        self,
    ):
        """A fresh (just-happened) trusted token still first-login inserts
        normally — the staleness guard only rejects tokens older than the
        window."""
        user_info = UserContextDto(
            sub="email|fresh",
            primary_email="fresh@example.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
            last_login_at=self.fresh_iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=88)
        self.users_repo.upsert_users.return_value = created

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, created)
        self.assertEqual(user_info.user_id, 88)

    async def test_create_or_swap_stale_token_with_confirmed_owner_still_routes(
        self,
    ):
        """The staleness guard protects only the first-login insert: a stale
        trusted token whose address a confirmed owner already holds still
        routes into that account at step 2.5, since no account is being
        forked."""
        stale_iat = int(time.time()) - 3600
        user_info = UserContextDto(
            sub="email|otp1",
            primary_email="owner@example.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
            last_login_at=stale_iat,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = MagicMock(
            spec=UserEmailsEntity, user_id=10, otp_confirmed=True
        )
        self.users_repo.get_user_by_user_id.return_value = self.user

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, self.user)
        self.assertEqual(user_info.user_id, 10)
        self.users_repo.upsert_users.assert_not_awaited()

    async def test_create_or_swap_first_login_none_last_login_still_inserts(self):
        """last_login_at=None (dev/test shims with no iat) skips the
        staleness guard entirely (nothing to compare) and still first-login
        inserts."""
        user_info = UserContextDto(
            sub="email|dev",
            primary_email="dev@example.com",
            identity_type=IdentityType.EXTERNAL,
            email_verified=True,
            last_login_at=None,
        )
        self.identities_repo.find_swappable_by_email.return_value = None
        self.emails_repo.get_confirmed_by_email.return_value = None
        created = MagicMock(spec=UsersEntity, user_id=66)
        self.users_repo.upsert_users.return_value = created

        result = await self.service.create_or_swap_user(self.session, user_info)

        self.assertIs(result, created)
        self.assertEqual(user_info.user_id, 66)

    # _iat_as_datetime helper
    async def test_iat_as_datetime_none(self):
        self.assertIsNone(_iat_as_datetime(None))

    async def test_iat_as_datetime_value(self):
        self.assertEqual(_iat_as_datetime(self.iat), self.iat_dt)


if __name__ == "__main__":
    unittest.main()
