import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from backend.admin.permission_admin_service import PermissionAdminService
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


class TestPermissionAdminService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.users = AsyncMock()
        self.perms = AsyncMock()
        self.service = PermissionAdminService(self.users, self.perms)
        self.session = AsyncMock()

    def test_catalog_is_full_enum_sorted(self):
        self.assertEqual(
            self.service.list_permission_catalog(),
            sorted(str(p) for p in Permission),
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

    async def test_list_permission_users_rejects_unknown_permission(self):
        with self.assertRaises(ValueError):
            await self.service.list_permission_users(
                self.session,
                "not.a.real.permission",
                include_revoked=False,
                granted_source=None,
            )

    async def test_list_permission_users_returns_grant_dtos(self):
        self.perms.get_users_with_permission.return_value = [
            _grant(5, 7, "permission.manage")
        ]
        out = await self.service.list_permission_users(
            self.session,
            "permission.manage",
            include_revoked=False,
            granted_source=None,
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].user_id, 7)
        self.assertTrue(out[0].is_active)

    async def test_list_users_wraps_repo_result(self):
        self.users.list_users.return_value = (
            [
                UsersEntity(
                    user_id=1,
                    primary_email="a@x.com",
                    first_name="A",
                    last_name="B",
                    is_active=True,
                    is_super_admin=False,
                )
            ],
            1,
        )
        out = await self.service.list_users(
            self.session, search=None, limit=20, offset=0
        )
        self.assertEqual(out.total, 1)
        self.assertEqual(out.users[0].primary_email, "a@x.com")

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
            await self.service.grant_permissions(
                self.session, 1, [], granted_by=9
            )

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

    async def test_grant_missing_user_raises(self):
        self.users.get_user_by_user_id.return_value = None
        with self.assertRaises(ValueError):
            await self.service.grant_permissions(
                self.session, 1, ["system.sync"], granted_by=9
            )

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

    async def test_revoke_rejects_empty_list(self):
        self.users.get_user_by_user_id.return_value = UsersEntity(user_id=1)
        with self.assertRaises(ValueError):
            await self.service.revoke_permissions(
                self.session, 1, [], revoked_by=9
            )

    async def test_revoke_missing_user_raises(self):
        self.users.get_user_by_user_id.return_value = None
        with self.assertRaises(ValueError):
            await self.service.revoke_permissions(
                self.session, 1, ["system.sync"], revoked_by=9
            )


if __name__ == "__main__":
    unittest.main()
