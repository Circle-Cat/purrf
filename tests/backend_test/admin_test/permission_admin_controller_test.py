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
)
from backend.common.permissions import Permission
from backend.dto.admin_permission_dto import (
    AuditListDto,
    UserListDto,
    UserPermissionsViewDto,
)


class _FakeSession:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


def _client(service, *, permissions):
    app = FastAPI()
    database = MagicMock()
    database.session = lambda: _FakeSession()
    controller = PermissionAdminController(service, database)

    @app.middleware("http")
    async def _inject(request: Request, call_next):
        request.state.user = MagicMock(
            permissions=permissions, user_id=1, sub="google-oauth2|1"
        )
        return await call_next(request)

    app.include_router(controller.router)
    return TestClient(app, raise_server_exceptions=False)


class TestPermissionAdminController(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.service.list_permission_catalog = MagicMock(
            return_value=["a.read", "b.read"]
        )
        self.service.list_users = AsyncMock(
            return_value=UserListDto(users=[], total=0)
        )
        self.service.get_user_permissions = AsyncMock(
            return_value=UserPermissionsViewDto(user_id=1, active=[], history=[])
        )
        self.service.list_permission_users = AsyncMock(return_value=[])
        self.service.list_audit = AsyncMock(
            return_value=AuditListDto(entries=[], total=0)
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


if __name__ == "__main__":
    unittest.main()
