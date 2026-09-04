import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from backend.admin.permission_admin_service import PermissionAdminService
from backend.common.permission_descriptions import PERMISSION_DESCRIPTIONS
from backend.common.permissions import Permission
from backend.entity.user_permissions_entity import UserPermissionsEntity
from backend.entity.users_entity import UsersEntity


def _grant(id, user_id, name, revoked=False):
    row = UserPermissionsEntity(
        user_id=user_id, permission_name=name, granted_source="admin", granted_by=9
    )
    row.id = id
    row.granted_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row.revoked_timestamp = (
        datetime(2026, 2, 1, tzinfo=timezone.utc) if revoked else None
    )
    row.revoked_by = 9 if revoked else None
    return row


def _marker(id, user_id, granted_by=9):
    """An active super_admin_set audit-marker row (permission_name='*')."""
    row = UserPermissionsEntity(
        user_id=user_id,
        permission_name="*",
        granted_source="super_admin_set",
        granted_by=granted_by,
    )
    row.id = id
    row.granted_timestamp = datetime(2026, 3, 1, tzinfo=timezone.utc)
    row.revoked_timestamp = None
    row.revoked_by = None
    return row


class TestPermissionAdminService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.users = AsyncMock()
        self.perms = AsyncMock()
        # Contact emails come from user_emails, not the legacy column.
        self.user_emails = AsyncMock()
        self.user_emails.get_contact_emails_by_user_ids.return_value = {}
        self.user_emails.get_contact_email.return_value = None
        self.service = PermissionAdminService(self.users, self.perms, self.user_emails)
        self.session = AsyncMock()

    def test_catalog_is_full_enum_sorted(self):
        catalog = self.service.list_permission_catalog()
        self.assertEqual(
            [entry.name for entry in catalog],
            sorted(str(p) for p in Permission),
        )
        for entry in catalog:
            self.assertEqual(
                entry.description, PERMISSION_DESCRIPTIONS[Permission(entry.name)]
            )

    async def test_get_user_permissions_splits_active_and_history(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(user_id=1)
        self.perms.get_grants_for_user.return_value = [
            _grant(1, 1, "internal_activity.read"),
            _grant(2, 1, "permission.manage", revoked=True),
        ]
        view = await self.service.get_user_permissions(self.session, 1)
        self.assertEqual(view.active, ["internal_activity.read"])
        self.assertEqual(len(view.history), 2)

    async def test_get_user_permissions_missing_user_raises(self):
        self.users.get_user_by_user_id.return_value = None
        with self.assertRaises(ValueError):
            await self.service.get_user_permissions(self.session, 999)

    async def test_list_users_wraps_repo_result(self):
        self.users.list_users.return_value = (
            [
                (
                    UsersEntity(
                        user_id=1,
                        first_name="A",
                        last_name="B",
                        is_active=True,
                        is_super_admin=False,
                    ),
                    False,  # is_internal
                )
            ],
            1,
        )
        self.user_emails.get_contact_emails_by_user_ids.return_value = {1: "a@x.com"}
        out = await self.service.list_users(
            self.session, search=None, limit=20, offset=0
        )
        self.assertEqual(out.total, 1)
        self.assertEqual(out.users[0].primary_email, "a@x.com")
        self.assertEqual(out.users[0].user_type, "external")
        self.assertIsNone(out.users[0].preferred_name)

    async def test_list_users_internal_user_gets_internal_type(self):
        self.users.list_users.return_value = (
            [
                (
                    UsersEntity(
                        user_id=2,
                        first_name="B",
                        last_name="C",
                        is_active=True,
                        is_super_admin=False,
                        preferred_name="Bee",
                    ),
                    True,  # is_internal
                )
            ],
            1,
        )
        out = await self.service.list_users(
            self.session, search=None, limit=20, offset=0
        )
        self.assertEqual(out.users[0].user_type, "internal")
        self.assertEqual(out.users[0].preferred_name, "Bee")

    async def test_list_users_forwards_sort_and_filter_params(self):
        """Service passes sort_by, order, is_super_admin, user_type through to repo."""
        self.users.list_users.return_value = ([], 0)
        await self.service.list_users(
            self.session,
            search="q",
            limit=10,
            offset=5,
            sort_by="last_name",
            order="desc",
            is_super_admin=True,
            user_type="internal",
        )
        self.users.list_users.assert_awaited_once()
        kwargs = self.users.list_users.await_args.kwargs
        self.assertEqual(kwargs["sort_by"], "last_name")
        self.assertEqual(kwargs["order"], "desc")
        self.assertEqual(kwargs["is_super_admin"], True)
        self.assertEqual(kwargs["user_type"], "internal")
        self.assertEqual(kwargs["search"], "q")
        self.assertEqual(kwargs["limit"], 10)
        self.assertEqual(kwargs["offset"], 5)

    async def test_list_users_defaults_sort_and_filter_params(self):
        """Service passes None defaults when sort/filter params are omitted."""
        self.users.list_users.return_value = ([], 0)
        await self.service.list_users(self.session, search=None, limit=20, offset=0)
        kwargs = self.users.list_users.await_args.kwargs
        self.assertIsNone(kwargs["sort_by"])
        self.assertEqual(kwargs["order"], "asc")
        self.assertIsNone(kwargs["is_super_admin"])
        self.assertIsNone(kwargs["user_type"])

    async def test_list_audit_wraps_repo_result(self):
        self.perms.list_audit.return_value = ([_grant(1, 1, "system.sync")], 1)
        out = await self.service.list_audit(
            self.session,
            user_id=None,
            permission_name=None,
            action=None,
            limit=50,
            offset=0,
        )
        self.assertEqual(out.total, 1)
        self.assertEqual(out.entries[0].permission_name, "system.sync")

    async def test_grant_rejects_unknown_permission(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(user_id=1)
        with self.assertRaises(ValueError):
            await self.service.grant_permissions(
                self.session, 1, ["not.real"], granted_by=9
            )

    async def test_grant_rejects_empty_list(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(user_id=1)
        with self.assertRaises(ValueError):
            await self.service.grant_permissions(self.session, 1, [], granted_by=9)

    async def test_grant_skips_already_active_and_grants_rest(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(user_id=1)
        self.perms.get_active_permission_names.return_value = {"permission.manage"}
        self.perms.get_grants_for_user.return_value = []
        await self.service.grant_permissions(
            self.session, 1, ["permission.manage", "system.sync"], granted_by=9
        )
        self.perms.grant.assert_awaited_once()
        args, kwargs = self.perms.grant.await_args
        granted = set(args[2]) if len(args) > 2 else set(kwargs["permission_names"])
        self.assertEqual(granted, {"system.sync"})
        self.session.commit.assert_awaited_once()

    async def test_grant_missing_user_raises(self):
        self.users.get_user_by_user_id.return_value = None
        with self.assertRaises(ValueError):
            await self.service.grant_permissions(
                self.session, 1, ["system.sync"], granted_by=9
            )
        self.session.commit.assert_not_awaited()

    async def test_revoke_rejects_unknown_permission(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(user_id=1)
        with self.assertRaises(ValueError):
            await self.service.revoke_permissions(
                self.session, 1, ["not.real"], revoked_by=9
            )

    async def test_revoke_calls_repo_and_returns_view(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(user_id=1)
        self.perms.get_grants_for_user.return_value = []
        view = await self.service.revoke_permissions(
            self.session, 1, ["system.sync"], revoked_by=9
        )
        self.perms.revoke.assert_awaited_once()
        self.assertEqual(view.user_id, 1)
        self.session.commit.assert_awaited_once()

    async def test_revoke_rejects_empty_list(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(user_id=1)
        with self.assertRaises(ValueError):
            await self.service.revoke_permissions(self.session, 1, [], revoked_by=9)

    async def test_revoke_missing_user_raises(self):
        self.users.get_user_by_user_id.return_value = None
        with self.assertRaises(ValueError):
            await self.service.revoke_permissions(
                self.session, 1, ["system.sync"], revoked_by=9
            )
        self.session.commit.assert_not_awaited()

    async def test_set_super_admin_updates_flag_and_writes_marker(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(
            user_id=2,
            first_name="S",
            last_name="A",
            is_active=True,
            is_super_admin=False,
        )
        self.users.set_super_admin.return_value = 1
        self.users.is_internal = AsyncMock(return_value=False)
        self.user_emails.get_contact_email.return_value = "s@x.com"
        dto = await self.service.set_super_admin(self.session, 2, granted_by=9)
        self.users.set_super_admin.assert_awaited_once_with(self.session, 2, True)
        self.perms.grant.assert_awaited_once()
        args, kwargs = self.perms.grant.await_args
        self.assertEqual(kwargs.get("granted_source"), "super_admin_set")
        names = args[2] if len(args) > 2 else kwargs["permission_names"]
        self.assertEqual(list(names), ["*"])
        self.assertTrue(dto.is_super_admin)
        self.assertEqual(dto.primary_email, "s@x.com")
        self.assertEqual(dto.user_type, "external")
        self.session.commit.assert_awaited_once()

    async def test_set_super_admin_missing_user_raises(self):
        self.users.get_user_by_user_id.return_value = None
        with self.assertRaises(ValueError):
            await self.service.set_super_admin(self.session, 999, granted_by=9)
        self.session.commit.assert_not_awaited()

    async def test_revoke_super_admin_self_raises(self):
        with self.assertRaises(ValueError):
            await self.service.revoke_super_admin(
                self.session, 9, caller_user_id=9, revoked_by=9
            )
        self.session.commit.assert_not_awaited()

    async def test_revoke_super_admin_clears_flag_and_marker(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(
            user_id=2,
            first_name="S",
            last_name="A",
            is_active=True,
            is_super_admin=True,
        )
        self.users.set_super_admin.return_value = 1
        self.users.is_internal = AsyncMock(return_value=False)
        dto = await self.service.revoke_super_admin(
            self.session, 2, caller_user_id=9, revoked_by=9
        )
        self.users.set_super_admin.assert_awaited_once_with(self.session, 2, False)
        self.perms.revoke_by_source.assert_awaited_once_with(
            self.session, 2, "super_admin_set", revoked_by=9
        )
        self.assertFalse(dto.is_super_admin)
        self.assertEqual(dto.user_type, "external")
        self.session.commit.assert_awaited_once()


class TestListUsersPermissionFilter(unittest.IsolatedAsyncioTestCase):
    """PUR-626: the permission is a filter on the user list, not a second view."""

    def setUp(self):
        self.users = AsyncMock()
        self.perms = AsyncMock()
        self.user_emails = AsyncMock()
        self.user_emails.get_contact_emails_by_user_ids.return_value = {}
        self.users.list_users.return_value = ([], 0)
        self.service = PermissionAdminService(self.users, self.perms, self.user_emails)
        self.session = AsyncMock()

    async def test_passes_the_permission_through_to_the_repository(self):
        await self.service.list_users(
            self.session,
            search=None,
            limit=20,
            offset=0,
            permission_name="permission.manage",
        )
        _, kwargs = self.users.list_users.await_args
        self.assertEqual(kwargs["permission_name"], "permission.manage")

    async def test_unknown_permission_is_rejected_before_the_query(self):
        with self.assertRaises(ValueError):
            await self.service.list_users(
                self.session,
                search=None,
                limit=20,
                offset=0,
                permission_name="not.a.real.permission",
            )
        self.users.list_users.assert_not_awaited()

    async def test_no_permission_filter_passes_none(self):
        await self.service.list_users(self.session, search=None, limit=20, offset=0)
        _, kwargs = self.users.list_users.await_args
        self.assertIsNone(kwargs["permission_name"])

    async def test_the_holders_view_is_gone(self):
        """The reverse lookup folded into list_users; nothing should call it."""
        self.assertFalse(hasattr(self.service, "list_permission_users"))


if __name__ == "__main__":
    unittest.main()
