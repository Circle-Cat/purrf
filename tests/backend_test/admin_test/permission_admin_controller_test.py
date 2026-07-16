import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.admin.permission_admin_controller import PermissionAdminController
from backend.common.api_endpoints import (
    ADMIN_AUDIT_PERMISSION_CHANGES_ENDPOINT,
    ADMIN_PERMISSIONS_ENDPOINT,
    ADMIN_USERS_ENDPOINT,
    ADMIN_USER_GRANT_PERMISSIONS_ENDPOINT,
    ADMIN_USER_REVOKE_PERMISSIONS_ENDPOINT,
    ADMIN_USER_SUPER_ADMIN_ENDPOINT,
)
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.common.permissions import Permission
from backend.dto.admin_permission_dto import (
    AdminUserDto,
    AuditListDto,
    UserListDto,
    UserPermissionsViewDto,
)


class _FakeSession:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


def _client(service, *, permissions, is_super_admin=False, user_id=1):
    app = FastAPI()
    database = MagicMock()
    database.session = lambda: _FakeSession()
    controller = PermissionAdminController(service, database)

    @app.middleware("http")
    async def _inject(request: Request, call_next):
        request.state.user = MagicMock(
            permissions=permissions,
            user_id=user_id,
            is_super_admin=is_super_admin,
            sub="google-oauth2|1",
        )
        return await call_next(request)

    app.include_router(controller.router)
    register_exception_handlers(app)
    return TestClient(app, raise_server_exceptions=False)


class TestPermissionAdminController(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.service.list_permission_catalog = MagicMock(
            return_value=["a.read", "b.read"]
        )
        self.service.list_users = AsyncMock(return_value=UserListDto(users=[], total=0))
        self.service.get_user_permissions = AsyncMock(
            return_value=UserPermissionsViewDto(user_id=1, active=[], history=[])
        )
        self.service.list_permission_users = AsyncMock(return_value=[])
        self.service.list_audit = AsyncMock(
            return_value=AuditListDto(entries=[], total=0)
        )
        self.service.grant_permissions = AsyncMock(
            return_value=UserPermissionsViewDto(
                user_id=2, active=["system.sync"], history=[]
            )
        )
        self.service.revoke_permissions = AsyncMock(
            return_value=UserPermissionsViewDto(user_id=2, active=[], history=[])
        )
        self.service.set_super_admin = AsyncMock(
            return_value=AdminUserDto(
                user_id=2,
                primary_email="s@x.com",
                first_name="S",
                last_name="A",
                is_active=True,
                is_super_admin=True,
                user_type="internal",
            )
        )
        self.service.revoke_super_admin = AsyncMock(
            return_value=AdminUserDto(
                user_id=2,
                primary_email="s@x.com",
                first_name="S",
                last_name="A",
                is_active=True,
                is_super_admin=False,
                user_type="external",
            )
        )

    def test_catalog_returns_enum(self):
        client = _client(self.service, permissions={Permission.PERMISSION_MANAGE})
        resp = client.get(ADMIN_PERMISSIONS_ENDPOINT)
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(resp.json()["data"]["permissions"], ["a.read", "b.read"])

    def test_users_passes_search_and_pagination(self):
        client = _client(self.service, permissions={Permission.PERMISSION_MANAGE})
        resp = client.get(
            ADMIN_USERS_ENDPOINT, params={"search": "al", "limit": 5, "offset": 10}
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.service.list_users.assert_awaited_once()
        kwargs = self.service.list_users.await_args.kwargs
        self.assertEqual(
            (kwargs["search"], kwargs["limit"], kwargs["offset"]), ("al", 5, 10)
        )

    def test_users_passes_sort_and_filter_params(self):
        """Controller forwards sort_by, order, is_super_admin, user_type to service."""
        client = _client(self.service, permissions={Permission.PERMISSION_MANAGE})
        resp = client.get(
            ADMIN_USERS_ENDPOINT,
            params={
                "sort_by": "last_name",
                "order": "desc",
                "is_super_admin": "true",
                "user_type": "internal",
            },
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.service.list_users.await_args.kwargs
        self.assertEqual(kwargs["sort_by"], "last_name")
        self.assertEqual(kwargs["order"], "desc")
        self.assertEqual(kwargs["is_super_admin"], True)
        self.assertEqual(kwargs["user_type"], "internal")

    def test_users_sort_filter_defaults_when_omitted(self):
        """Controller sends None defaults for sort/filter when params are absent."""
        client = _client(self.service, permissions={Permission.PERMISSION_MANAGE})
        resp = client.get(ADMIN_USERS_ENDPOINT)
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.service.list_users.await_args.kwargs
        self.assertIsNone(kwargs["sort_by"])
        self.assertEqual(kwargs["order"], "asc")
        self.assertIsNone(kwargs["is_super_admin"])
        self.assertIsNone(kwargs["user_type"])

    def test_audit_passes_filters(self):
        client = _client(self.service, permissions={Permission.PERMISSION_MANAGE})
        resp = client.get(
            ADMIN_AUDIT_PERMISSION_CHANGES_ENDPOINT,
            params={"action": "revoked", "user_id": 7},
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.service.list_audit.await_args.kwargs
        self.assertEqual((kwargs["action"], kwargs["user_id"]), ("revoked", 7))

    def test_without_permission_manage_is_403(self):
        client = _client(self.service, permissions=frozenset())
        resp = client.get(ADMIN_PERMISSIONS_ENDPOINT)
        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_grant_passes_names_and_granted_by(self):
        client = _client(
            self.service, permissions={Permission.PERMISSION_MANAGE}, user_id=9
        )
        resp = client.post(
            ADMIN_USER_GRANT_PERMISSIONS_ENDPOINT.format(user_id=2),
            json={"permissionNames": ["system.sync"]},
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.service.grant_permissions.assert_awaited_once()
        args, kwargs = self.service.grant_permissions.await_args
        self.assertEqual(args[1], 2)
        self.assertEqual(args[2], ["system.sync"])
        self.assertEqual(kwargs["granted_by"], 9)

    def test_revoke_passes_names_and_revoked_by(self):
        client = _client(
            self.service, permissions={Permission.PERMISSION_MANAGE}, user_id=9
        )
        resp = client.post(
            ADMIN_USER_REVOKE_PERMISSIONS_ENDPOINT.format(user_id=2),
            json={"permissionNames": ["system.sync"]},
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.service.revoke_permissions.assert_awaited_once()
        kwargs = self.service.revoke_permissions.await_args.kwargs
        self.assertEqual(kwargs["revoked_by"], 9)

    def test_grant_without_permission_manage_is_403(self):
        client = _client(self.service, permissions=frozenset())
        resp = client.post(
            ADMIN_USER_GRANT_PERMISSIONS_ENDPOINT.format(user_id=2),
            json={"permissionNames": ["system.sync"]},
        )
        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_set_super_admin_requires_caller_super_admin(self):
        client = _client(
            self.service,
            permissions={Permission.PERMISSION_MANAGE},
            is_super_admin=False,
        )
        resp = client.post(ADMIN_USER_SUPER_ADMIN_ENDPOINT.format(user_id=2))
        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)
        self.service.set_super_admin.assert_not_awaited()

    def test_set_super_admin_allows_super_admin_caller(self):
        client = _client(
            self.service,
            permissions={Permission.PERMISSION_MANAGE},
            is_super_admin=True,
            user_id=9,
        )
        resp = client.post(ADMIN_USER_SUPER_ADMIN_ENDPOINT.format(user_id=2))
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.service.set_super_admin.assert_awaited_once()
        self.assertEqual(
            self.service.set_super_admin.await_args.kwargs["granted_by"], 9
        )

    def test_revoke_super_admin_passes_caller_id(self):
        client = _client(
            self.service,
            permissions={Permission.SUPER_ADMIN_REVOKE},
            user_id=9,
        )
        resp = client.delete(ADMIN_USER_SUPER_ADMIN_ENDPOINT.format(user_id=2))
        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.service.revoke_super_admin.await_args.kwargs
        self.assertEqual(kwargs["caller_user_id"], 9)
        self.assertEqual(kwargs["revoked_by"], 9)

    def test_revoke_super_admin_without_permission_is_403(self):
        client = _client(self.service, permissions={Permission.PERMISSION_MANAGE})
        resp = client.delete(ADMIN_USER_SUPER_ADMIN_ENDPOINT.format(user_id=2))
        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
