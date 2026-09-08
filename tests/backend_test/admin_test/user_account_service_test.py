import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from backend.admin.user_account_service import UserAccountService
from backend.common.user_enums import BlockRequestStatus
from backend.entity.block_request_entity import BlockRequestEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.entity.users_entity import UsersEntity

ME = 1
BLOCKED = 2
REVIEWER = 3
OTHER_ADMIN = 4
TARGET = 5


def _user(user_id, *, first="Yanpei", last="Wang", preferred=None, **flags):
    """A real entity, never a bare MagicMock: every attribute of a MagicMock is
    truthy, which silently turns is_active/is_blocked checks into whatever the
    caller hoped for."""
    row = UsersEntity(
        first_name=first,
        last_name=last,
        preferred_name=preferred,
        timezone="UTC",
        is_active=flags.get("is_active", True),
        updated_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    row.user_id = user_id
    row.is_super_admin = flags.get("is_super_admin", False)
    row.is_blocked = flags.get("is_blocked", False)
    row.blocked_by = flags.get("blocked_by")
    row.blocked_at = flags.get("blocked_at")
    row.blocked_reason = flags.get("blocked_reason")
    row.deactivated_by = flags.get("deactivated_by")
    row.deactivated_at = flags.get("deactivated_at")
    row.deactivated_reason = flags.get("deactivated_reason")
    return row


def _pending(request_id, target_user_id, reviewer_id):
    row = BlockRequestEntity(
        target_user_id=target_user_id,
        raised_by=OTHER_ADMIN,
        raised_from="recruiting_board",
        reason="second no-show",
        reviewer_id=reviewer_id,
        status=BlockRequestStatus.PENDING,
    )
    row.request_id = request_id
    return row


class TestUserAccountService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.users = AsyncMock()
        self.user_emails = AsyncMock()
        self.user_identities = AsyncMock()
        self.block_requests = AsyncMock()
        self.logger = Mock()

        self.user_emails.get_contact_emails_by_user_ids.return_value = {}
        self.users.get_all_by_ids.return_value = []
        self.block_requests.list_pending_for_reviewer.return_value = []

        self.service = UserAccountService(
            users_repository=self.users,
            user_emails_repository=self.user_emails,
            user_identities_repository=self.user_identities,
            block_request_repository=self.block_requests,
            logger=self.logger,
        )
        self.session = AsyncMock()

    # ---- writes -----------------------------------------------------------

    async def test_deactivate_self_is_rejected(self):
        """Deactivating yourself locks the only door back in."""
        self.users.get_user_by_user_id.return_value = _user(ME)

        with self.assertRaises(PermissionError):
            await self.service.deactivate(
                self.session, actor_id=ME, user_id=ME, note=None
            )

        self.users.deactivate.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_deactivate_unknown_user_raises(self):
        self.users.get_user_by_user_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.deactivate(
                self.session, actor_id=ME, user_id=999999, note=None
            )

        self.users.deactivate.assert_not_awaited()

    async def test_deactivate_writes_and_commits(self):
        self.users.get_user_by_user_id.return_value = _user(TARGET)

        await self.service.deactivate(
            self.session, actor_id=ME, user_id=TARGET, note="requested by email"
        )

        self.users.deactivate.assert_awaited_once_with(
            self.session, TARGET, ME, "requested by email"
        )
        self.session.commit.assert_awaited_once()

    async def test_reactivate_self_is_allowed(self):
        """Only deactivation is guarded: turning your own account back on
        cannot lock anyone out."""
        self.users.get_user_by_user_id.return_value = _user(ME, is_active=False)

        await self.service.reactivate(self.session, actor_id=ME, user_id=ME)

        self.users.reactivate.assert_awaited_once_with(self.session, ME)
        self.session.commit.assert_awaited_once()

    async def test_reactivate_unknown_user_raises(self):
        self.users.get_user_by_user_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.reactivate(self.session, actor_id=ME, user_id=999999)

    async def test_unblock_twice_neither_raises_nor_short_circuits(self):
        """The service does not guard against unblocking someone who is not
        blocked -- it always writes and always commits. Idempotency itself is a
        property of the repository's UPDATE, and is tested there, not here."""
        self.users.get_user_by_user_id.return_value = _user(TARGET)

        await self.service.unblock(self.session, actor_id=ME, user_id=TARGET)
        await self.service.unblock(self.session, actor_id=ME, user_id=TARGET)

        self.assertEqual(self.users.clear_block.await_count, 2)
        self.assertEqual(self.session.commit.await_count, 2)

    async def test_unblock_unknown_user_raises(self):
        self.users.get_user_by_user_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.unblock(self.session, actor_id=ME, user_id=999999)

    # ---- list -------------------------------------------------------------

    async def test_by_name_fields_are_resolved(self):
        """Permission holders/Audit showing bare user_id is one of the defects
        this project exists to fix -- new code must never reproduce it."""
        blocked = _user(
            BLOCKED,
            first="Sam",
            last="Stone",
            is_blocked=True,
            blocked_by=ME,
            blocked_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            blocked_reason="cheated",
        )
        self.users.list_users.return_value = ([(blocked, True)], 1)
        self.users.get_all_by_ids.return_value = [_user(ME)]

        rows, total = await self.service.list_accounts(
            self.session, caller_id=ME, status="blocked", limit=50, offset=0
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].blocked_by, ME)
        self.assertEqual(rows[0].blocked_by_name, "Yanpei Wang")
        # One batched lookup for the whole page, never one query per row.
        self.users.get_all_by_ids.assert_awaited_once()

    async def test_by_name_uses_preferred_name(self):
        """blocked_by/deactivated_by name a colleague acting, and PUR-609 puts
        colleagues on preferred_name."""
        row = _user(BLOCKED, is_blocked=True, blocked_by=ME, blocked_reason="cheated")
        self.users.list_users.return_value = ([(row, True)], 1)
        self.users.get_all_by_ids.return_value = [_user(ME, preferred="Pei")]

        rows, _ = await self.service.list_accounts(
            self.session, caller_id=ME, limit=50, offset=0
        )

        self.assertEqual(rows[0].blocked_by_name, "Pei")

    async def test_unresolvable_actor_leaves_the_name_none(self):
        """An audit trail can outlive the account it names."""
        row = _user(BLOCKED, is_blocked=True, blocked_by=404)
        self.users.list_users.return_value = ([(row, True)], 1)
        self.users.get_all_by_ids.return_value = []

        rows, _ = await self.service.list_accounts(
            self.session, caller_id=ME, limit=50, offset=0
        )

        self.assertEqual(rows[0].blocked_by, 404)
        self.assertIsNone(rows[0].blocked_by_name)

    async def test_page_with_no_actors_skips_the_lookup(self):
        self.users.list_users.return_value = ([(_user(TARGET), False)], 1)

        await self.service.list_accounts(self.session, caller_id=ME, limit=50, offset=0)

        self.users.get_all_by_ids.assert_not_awaited()

    async def test_pending_flag_is_scoped_to_caller(self):
        """A request names one reviewer; nobody else may even see it exists."""
        self.users.list_users.return_value = ([(_user(TARGET), False)], 1)
        self.block_requests.list_pending_for_reviewer.return_value = [
            _pending(1, TARGET, REVIEWER)
        ]

        rows, _ = await self.service.list_accounts(
            self.session, caller_id=REVIEWER, limit=50, offset=0
        )
        self.assertTrue(rows[0].has_pending_block_request)

        self.block_requests.list_pending_for_reviewer.return_value = []
        rows, _ = await self.service.list_accounts(
            self.session, caller_id=OTHER_ADMIN, limit=50, offset=0
        )
        self.assertFalse(rows[0].has_pending_block_request)

        self.block_requests.list_pending_for_reviewer.assert_awaited_with(
            self.session, OTHER_ADMIN
        )

    async def test_pending_flag_is_one_query_for_the_page(self):
        self.users.list_users.return_value = (
            [(_user(TARGET), False), (_user(BLOCKED), False)],
            2,
        )

        await self.service.list_accounts(
            self.session, caller_id=REVIEWER, limit=50, offset=0
        )

        self.assertEqual(self.block_requests.list_pending_for_reviewer.await_count, 1)

    async def test_status_active_means_neither_deactivated_nor_blocked(self):
        self.users.list_users.return_value = ([], 0)

        await self.service.list_accounts(
            self.session, caller_id=ME, status="active", limit=50, offset=0
        )

        kwargs = self.users.list_users.await_args.kwargs
        self.assertIs(kwargs["is_active"], True)
        self.assertIs(kwargs["is_blocked"], False)

    async def test_status_deactivated_reads_the_active_flag_only(self):
        """Blocked users are not hidden from the deactivated view by accident:
        the two states are independent."""
        self.users.list_users.return_value = ([], 0)

        await self.service.list_accounts(
            self.session, caller_id=ME, status="deactivated", limit=50, offset=0
        )

        kwargs = self.users.list_users.await_args.kwargs
        self.assertIs(kwargs["is_active"], False)
        self.assertIsNone(kwargs["is_blocked"])

    async def test_status_blocked_reads_the_block_flag_only(self):
        self.users.list_users.return_value = ([], 0)

        await self.service.list_accounts(
            self.session, caller_id=ME, status="blocked", limit=50, offset=0
        )

        kwargs = self.users.list_users.await_args.kwargs
        self.assertIs(kwargs["is_blocked"], True)
        self.assertIsNone(kwargs["is_active"])

    async def test_blocked_view_is_ordered_by_when_they_were_blocked(self):
        """Filtering to blocked accounts asks "who did we block, and when" --
        the job the retired blacklist page did, ordered the same way. Ordering
        that page by user_id buries the most recent block on an arbitrary
        page."""
        self.users.list_users.return_value = ([], 0)

        await self.service.list_accounts(
            self.session, caller_id=ME, status="blocked", limit=50, offset=0
        )

        kwargs = self.users.list_users.await_args.kwargs
        self.assertEqual(kwargs["sort_by"], "blocked_at")
        self.assertEqual(kwargs["order"], "desc")

    async def test_other_views_keep_the_default_order(self):
        self.users.list_users.return_value = ([], 0)

        await self.service.list_accounts(
            self.session, caller_id=ME, status="active", limit=50, offset=0
        )

        self.assertIsNone(self.users.list_users.await_args.kwargs["sort_by"])

    async def test_no_status_filters_nothing(self):
        self.users.list_users.return_value = ([], 0)

        await self.service.list_accounts(self.session, caller_id=ME, limit=50, offset=0)

        kwargs = self.users.list_users.await_args.kwargs
        self.assertIsNone(kwargs["is_active"])
        self.assertIsNone(kwargs["is_blocked"])

    async def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError):
            await self.service.list_accounts(
                self.session, caller_id=ME, status="banned", limit=50, offset=0
            )

    async def test_blocked_reason_search_is_passed_through(self):
        self.users.list_users.return_value = ([], 0)

        await self.service.list_accounts(
            self.session,
            caller_id=ME,
            search="noshow",
            search_blocked_reason=True,
            limit=50,
            offset=0,
        )

        self.assertIs(
            self.users.list_users.await_args.kwargs["search_blocked_reason"], True
        )

    # ---- sign-in methods --------------------------------------------------

    async def test_sign_in_methods_for_passwordless_only_user(self):
        """A user who has only ever used email codes has no user_identities
        row. The page must say so explicitly rather than render a blank block."""
        self.users.get_user_by_user_id.return_value = _user(TARGET)
        email = UserEmailsEntity(
            user_id=TARGET,
            email="a@example.com",
            otp_confirmed=True,
            is_primary=True,
        )
        email.last_login_at = None
        self.user_emails.list_by_user_id.return_value = [email]
        self.user_identities.list_by_user_id.return_value = []

        view = await self.service.get_sign_in_methods(self.session, TARGET)

        self.assertEqual(view.identities, [])
        self.assertEqual(len(view.emails), 1)
        self.assertEqual(view.emails[0].email, "a@example.com")

    async def test_sign_in_methods_carries_identities(self):
        self.users.get_user_by_user_id.return_value = _user(TARGET)
        self.user_emails.list_by_user_id.return_value = []
        identity = UserIdentitiesEntity(
            user_id=TARGET,
            subject_identifier="google-oauth2|1",
            email_claim="a@example.com",
        )
        identity.linked_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        identity.last_login_at = None
        self.user_identities.list_by_user_id.return_value = [identity]

        view = await self.service.get_sign_in_methods(self.session, TARGET)

        self.assertEqual(view.identities[0].subject_identifier, "google-oauth2|1")
        self.assertEqual(view.identities[0].email_claim, "a@example.com")

    async def test_sign_in_methods_unknown_user_raises(self):
        self.users.get_user_by_user_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.get_sign_in_methods(self.session, 999999)


if __name__ == "__main__":
    unittest.main()
