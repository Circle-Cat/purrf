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


def _route(holders, markers):
    """
    side_effect for get_users_with_permission: the reverse-lookup uses one call
    for the requested permission and a second (name='*') for the super-admin
    markers; route each to its own canned result.
    """

    def _impl(session, name, *, include_revoked=False, granted_source=None):
        return markers if name == "*" else holders

    return _impl


class TestPermissionAdminService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.users = AsyncMock()
        self.perms = AsyncMock()
        self.service = PermissionAdminService(self.users, self.perms)
        self.session = AsyncMock()
        # Default: no super admins (most tests are about plain grant rows).
        self.users.get_super_admins.return_value = []

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
        self.assertFalse(out[0].is_super_admin)

    async def test_list_permission_users_super_admin_appears_as_derived(self):
        """A super admin with no real grant shows up as a derived holder."""
        self.perms.get_users_with_permission.side_effect = _route([], [_marker(1, 7)])
        self.users.get_super_admins.return_value = [
            UsersEntity(user_id=7, is_super_admin=True)
        ]
        out = await self.service.list_permission_users(
            self.session,
            "permission.manage",
            include_revoked=False,
            granted_source=None,
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].user_id, 7)
        self.assertEqual(out[0].granted_source, "super_admin")
        self.assertEqual(out[0].permission_name, "permission.manage")
        self.assertTrue(out[0].is_super_admin)
        self.assertTrue(out[0].is_active)
        # Metadata sourced from the audit marker.
        self.assertEqual(out[0].id, 1)
        self.assertEqual(out[0].granted_by, 9)
        self.assertIsNotNone(out[0].granted_timestamp)

    async def test_list_permission_users_super_admin_with_grant_not_duplicated(self):
        """A super admin holding a real active grant shows once, source-flagged."""
        self.perms.get_users_with_permission.side_effect = _route(
            [_grant(5, 7, "permission.manage")], [_marker(1, 7)]
        )
        self.users.get_super_admins.return_value = [
            UsersEntity(user_id=7, is_super_admin=True)
        ]
        out = await self.service.list_permission_users(
            self.session,
            "permission.manage",
            include_revoked=False,
            granted_source=None,
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].granted_source, "admin")  # real source kept
        self.assertTrue(out[0].is_super_admin)  # still annotated

    async def test_list_permission_users_derived_without_marker_uses_sentinels(self):
        """A seeded super admin (no marker) gets sentinel id and null metadata."""
        self.perms.get_users_with_permission.side_effect = _route([], [])
        self.users.get_super_admins.return_value = [
            UsersEntity(user_id=7, is_super_admin=True)
        ]
        out = await self.service.list_permission_users(
            self.session,
            "permission.manage",
            include_revoked=False,
            granted_source=None,
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].id, -7)
        self.assertIsNone(out[0].granted_by)
        self.assertIsNone(out[0].granted_timestamp)
        self.assertTrue(out[0].is_super_admin)

    async def test_list_permission_users_source_filter_excludes_derived(self):
        """A non-super_admin source filter never surfaces derived holders."""
        self.perms.get_users_with_permission.side_effect = _route(
            [_grant(5, 7, "permission.manage")], [_marker(1, 8)]
        )
        self.users.get_super_admins.return_value = [
            UsersEntity(user_id=8, is_super_admin=True)
        ]
        out = await self.service.list_permission_users(
            self.session,
            "permission.manage",
            include_revoked=False,
            granted_source="admin",
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].user_id, 7)
        self.users.get_super_admins.assert_not_awaited()

    async def test_list_permission_users_source_filter_super_admin_only_derived(self):
        """granted_source='super_admin' returns only the derived holders."""
        self.perms.get_users_with_permission.side_effect = _route([], [_marker(1, 8)])
        self.users.get_super_admins.return_value = [
            UsersEntity(user_id=8, is_super_admin=True)
        ]
        out = await self.service.list_permission_users(
            self.session,
            "permission.manage",
            include_revoked=False,
            granted_source="super_admin",
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].user_id, 8)
        self.assertEqual(out[0].granted_source, "super_admin")

    async def test_list_permission_users_revoked_grant_coexists_with_derived(self):
        """A super admin with only a revoked grant: revoked row plus derived row."""
        self.perms.get_users_with_permission.side_effect = _route(
            [_grant(5, 7, "permission.manage", revoked=True)], [_marker(1, 7)]
        )
        self.users.get_super_admins.return_value = [
            UsersEntity(user_id=7, is_super_admin=True)
        ]
        out = await self.service.list_permission_users(
            self.session, "permission.manage", include_revoked=True, granted_source=None
        )
        self.assertEqual(len(out), 2)
        by_source = {g.granted_source: g for g in out}
        self.assertEqual(set(by_source), {"admin", "super_admin"})
        self.assertFalse(by_source["admin"].is_active)
        self.assertTrue(by_source["super_admin"].is_active)
        self.assertTrue(all(g.is_super_admin for g in out))

    async def test_list_users_wraps_repo_result(self):
        self.users.list_users.return_value = (
            [
                (
                    UsersEntity(
                        user_id=1,
                        primary_email="a@x.com",
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
                        primary_email="b@circlecat.org",
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
            primary_email="s@x.com",
            first_name="S",
            last_name="A",
            is_active=True,
            is_super_admin=False,
        )
        self.users.set_super_admin.return_value = 1
        self.users.is_internal = AsyncMock(return_value=False)
        dto = await self.service.set_super_admin(self.session, 2, granted_by=9)
        self.users.set_super_admin.assert_awaited_once_with(self.session, 2, True)
        self.perms.grant.assert_awaited_once()
        args, kwargs = self.perms.grant.await_args
        self.assertEqual(kwargs.get("granted_source"), "super_admin_set")
        names = args[2] if len(args) > 2 else kwargs["permission_names"]
        self.assertEqual(list(names), ["*"])
        self.assertTrue(dto.is_super_admin)
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
            primary_email="s@x.com",
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


if __name__ == "__main__":
    unittest.main()
