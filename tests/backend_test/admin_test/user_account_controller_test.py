import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.admin.user_account_controller import UserAccountController
from backend.common.api_endpoints import (
    ADMIN_ACCOUNT_BLOCK_ENDPOINT,
    ADMIN_ACCOUNT_DEACTIVATE_ENDPOINT,
    ADMIN_ACCOUNT_REACTIVATE_ENDPOINT,
    ADMIN_ACCOUNT_SIGN_IN_METHODS_ENDPOINT,
    ADMIN_ACCOUNT_UNBLOCK_ENDPOINT,
    ADMIN_ACCOUNTS_ENDPOINT,
)
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.common.permissions import SUPER_ADMIN_PERMISSIONS, Permission
from backend.dto.user_account_dto import UserSignInMethodsDto

CALLER = 1
TARGET = 7


class _FakeSession:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


def _client(service, blocks, *, permissions, is_super_admin=False, user_id=CALLER):
    app = FastAPI()
    database = MagicMock()
    database.session = lambda: _FakeSession()
    controller = UserAccountController(service, blocks, database)

    @app.middleware("http")
    async def _inject(request: Request, call_next):
        # Explicit booleans, never a bare MagicMock: every attribute of one is
        # truthy, which has previously turned a gate into a blanket 403.
        request.state.user = MagicMock(
            permissions=permissions,
            user_id=user_id,
            is_super_admin=is_super_admin,
            is_active=True,
            is_blocked=False,
            sub="google-oauth2|1",
        )
        return await call_next(request)

    app.include_router(controller.router)
    register_exception_handlers(app)
    return TestClient(app, raise_server_exceptions=False)


# (method, path, body). The body must be one the route accepts: a rejected
# body answers 400 before the gate ever runs, which would let this suite pass
# while the gate was wide open.
_ROUTES = [
    ("get", ADMIN_ACCOUNTS_ENDPOINT, None),
    ("get", ADMIN_ACCOUNT_SIGN_IN_METHODS_ENDPOINT.format(user_id=TARGET), None),
    ("post", ADMIN_ACCOUNT_DEACTIVATE_ENDPOINT.format(user_id=TARGET), {}),
    ("post", ADMIN_ACCOUNT_REACTIVATE_ENDPOINT.format(user_id=TARGET), None),
    ("post", ADMIN_ACCOUNT_UNBLOCK_ENDPOINT.format(user_id=TARGET), None),
    ("post", ADMIN_ACCOUNT_BLOCK_ENDPOINT.format(user_id=TARGET), {"reason": "r"}),
]


class TestUserAccountController(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.service.list_accounts = AsyncMock(return_value=([], 0))
        self.service.get_sign_in_methods = AsyncMock(
            return_value=UserSignInMethodsDto(emails=[], identities=[])
        )
        self.service.deactivate = AsyncMock(return_value=None)
        self.service.reactivate = AsyncMock(return_value=None)
        self.service.unblock = AsyncMock(return_value=None)
        self.blocks = MagicMock()
        self.blocks.block_directly = AsyncMock(return_value=None)

    def _admin(self):
        return _client(
            self.service, self.blocks, permissions={Permission.USER_ADMIN.value}
        )

    # -- the gate -----------------------------------------------------------

    def test_every_route_requires_user_admin(self):
        client = _client(self.service, self.blocks, permissions=set())
        for method, path, body in _ROUTES:
            with self.subTest(path=path):
                kwargs = {"json": body} if body is not None else {}
                resp = getattr(client, method)(path, **kwargs)
                self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_a_permitted_caller_reaches_every_route(self):
        """The other half of the gate test: without this, a route that answered
        403 for everyone would look correctly gated."""
        client = self._admin()
        for method, path, body in _ROUTES:
            with self.subTest(path=path):
                kwargs = {"json": body} if body is not None else {}
                resp = getattr(client, method)(path, **kwargs)
                self.assertEqual(resp.status_code, HTTPStatus.OK)

    def test_permission_manage_alone_cannot_reach_the_console(self):
        """PERMISSION_MANAGE is not a bundle -- only is_super_admin expands to
        the full enum. Every route, not just the list: the empty-permission
        loop above only proves the routes are not public, so an accidental
        ``or PERMISSION_MANAGE`` on one of them would go unnoticed."""
        client = _client(
            self.service,
            self.blocks,
            permissions={Permission.PERMISSION_MANAGE.value},
        )

        for method, path, body in _ROUTES:
            with self.subTest(path=path):
                kwargs = {"json": body} if body is not None else {}
                resp = getattr(client, method)(path, **kwargs)
                self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_super_admin_passes(self):
        # AuthMiddleware hands a super admin the whole enum; the decorator only
        # ever reads `permissions`, so modelling the flag alone would test
        # nothing that runs in production.
        client = _client(
            self.service,
            self.blocks,
            permissions=SUPER_ADMIN_PERMISSIONS,
            is_super_admin=True,
        )

        resp = client.get(ADMIN_ACCOUNTS_ENDPOINT)

        self.assertEqual(resp.status_code, HTTPStatus.OK)

    # -- delegation ---------------------------------------------------------

    def test_list_scopes_the_pending_flag_to_the_caller(self):
        resp = self._admin().get(f"{ADMIN_ACCOUNTS_ENDPOINT}?status=blocked&limit=5")

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.service.list_accounts.await_args.kwargs
        self.assertEqual(kwargs["caller_id"], CALLER)
        self.assertEqual(kwargs["status"], "blocked")
        self.assertEqual(kwargs["limit"], 5)

    def test_list_searches_block_reasons(self):
        """The deleted blacklist page could search by reason; the console that
        replaces it must not lose that."""
        self._admin().get(f"{ADMIN_ACCOUNTS_ENDPOINT}?search=noshow")

        self.assertIs(
            self.service.list_accounts.await_args.kwargs["search_blocked_reason"],
            True,
        )

    def test_sign_in_methods_delegates(self):
        resp = self._admin().get(
            ADMIN_ACCOUNT_SIGN_IN_METHODS_ENDPOINT.format(user_id=TARGET)
        )

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.service.get_sign_in_methods.assert_awaited_once()
        self.assertEqual(self.service.get_sign_in_methods.await_args.args[1], TARGET)

    def test_deactivate_passes_the_actor_and_the_note(self):
        resp = self._admin().post(
            ADMIN_ACCOUNT_DEACTIVATE_ENDPOINT.format(user_id=TARGET),
            json={"note": "requested by email"},
        )

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.service.deactivate.await_args.kwargs
        self.assertEqual(kwargs["actor_id"], CALLER)
        self.assertEqual(kwargs["user_id"], TARGET)
        self.assertEqual(kwargs["note"], "requested by email")

    def test_deactivate_note_may_be_omitted(self):
        resp = self._admin().post(
            ADMIN_ACCOUNT_DEACTIVATE_ENDPOINT.format(user_id=TARGET), json={}
        )

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertIsNone(self.service.deactivate.await_args.kwargs["note"])

    def test_reactivate_delegates(self):
        resp = self._admin().post(
            ADMIN_ACCOUNT_REACTIVATE_ENDPOINT.format(user_id=TARGET)
        )

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(self.service.reactivate.await_args.kwargs["user_id"], TARGET)

    def test_unblock_delegates(self):
        resp = self._admin().post(ADMIN_ACCOUNT_UNBLOCK_ENDPOINT.format(user_id=TARGET))

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(self.service.unblock.await_args.kwargs["user_id"], TARGET)

    def test_block_delegates_to_the_block_service(self):
        resp = self._admin().post(
            ADMIN_ACCOUNT_BLOCK_ENDPOINT.format(user_id=TARGET),
            json={"reason": "second no-show"},
        )

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.blocks.block_directly.await_args.kwargs
        self.assertEqual(kwargs["actor_id"], CALLER)
        self.assertEqual(kwargs["user_id"], TARGET)
        self.assertEqual(kwargs["reason"], "second no-show")

    def test_block_rejects_blank_reason(self):
        resp = self._admin().post(
            ADMIN_ACCOUNT_BLOCK_ENDPOINT.format(user_id=TARGET),
            json={"reason": "   "},
        )

        self.assertEqual(resp.status_code, HTTPStatus.BAD_REQUEST)
        self.blocks.block_directly.assert_not_awaited()

    # -- error mapping ------------------------------------------------------

    def test_acting_on_yourself_is_a_403(self):
        self.service.deactivate = AsyncMock(side_effect=PermissionError("no"))

        resp = self._admin().post(
            ADMIN_ACCOUNT_DEACTIVATE_ENDPOINT.format(user_id=CALLER), json={}
        )

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_unknown_user_is_a_400(self):
        self.service.reactivate = AsyncMock(side_effect=ValueError("User not found"))

        resp = self._admin().post(
            ADMIN_ACCOUNT_REACTIVATE_ENDPOINT.format(user_id=999999)
        )

        self.assertEqual(resp.status_code, HTTPStatus.BAD_REQUEST)

    def test_unknown_status_is_a_400(self):
        self.service.list_accounts = AsyncMock(side_effect=ValueError("Unknown status"))

        resp = self._admin().get(f"{ADMIN_ACCOUNTS_ENDPOINT}?status=banned")

        self.assertEqual(resp.status_code, HTTPStatus.BAD_REQUEST)

    # -- route shape --------------------------------------------------------

    def test_the_three_writes_are_single_verb_posts(self):
        app = FastAPI()
        database = MagicMock()
        database.session = lambda: _FakeSession()
        controller = UserAccountController(self.service, self.blocks, database)
        app.include_router(controller.router)
        methods_by_path = {
            route.path: route.methods
            for route in app.routes
            if hasattr(route, "methods")
        }

        for endpoint in (
            ADMIN_ACCOUNT_DEACTIVATE_ENDPOINT,
            ADMIN_ACCOUNT_REACTIVATE_ENDPOINT,
            ADMIN_ACCOUNT_UNBLOCK_ENDPOINT,
            ADMIN_ACCOUNT_BLOCK_ENDPOINT,
        ):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(methods_by_path[endpoint], {"POST"})


if __name__ == "__main__":
    unittest.main()
