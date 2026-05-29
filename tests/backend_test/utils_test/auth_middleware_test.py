import asyncio
import unittest
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from backend.common.user_role import UserRole
from backend.utils.auth_middleware import AuthMiddleware


def make_user_context(
    sub="user_123", roles=None, last_login_at=None, identity_type="external"
):
    """
    Build a UserContextDto-like object. The middleware accesses attributes
    (sub / identity_type / roles / last_login_at / user_id), not dict keys, so
    we use a SimpleNamespace rather than a plain dict.
    """
    return SimpleNamespace(
        sub=sub,
        primary_email="test@example.com",
        identity_type=identity_type,
        roles=roles if roles is not None else [UserRole.MANAGER],
        last_login_at=last_login_at,
        user_id=None,
    )


def make_session_mock():
    """
    Fake the `database.session()` async context manager plus the
    `session.begin()` (transaction) and `session.begin_nested()` (savepoint)
    async context managers.

    database.session()      -> async CM yielding `session`
    session.begin()         -> async CM (return value unused)
    session.begin_nested()  -> async CM (savepoint; return value unused)
    """
    session = MagicMock(name="session")

    session_cm = MagicMock(name="session_cm")
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    begin_cm = MagicMock(name="begin_cm")
    begin_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    begin_cm.__aexit__ = AsyncMock(return_value=False)

    nested_cm = MagicMock(name="begin_nested_cm")
    nested_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    nested_cm.__aexit__ = AsyncMock(return_value=False)

    session.begin = MagicMock(return_value=begin_cm)
    session.begin_nested = MagicMock(return_value=nested_cm)

    database = MagicMock(name="database")
    database.session = MagicMock(return_value=session_cm)
    return database, session


class TestAuthMiddleware(unittest.TestCase):
    def setUp(self):
        """
        Runs before each test.

        Initializes a Starlette application containing test routes,
        and prepares mocked auth_service / database / user_identity_service.
        """
        self.mock_auth_service = MagicMock()
        self.mock_database, self.mock_session = make_session_mock()
        self.mock_user_identity_service = MagicMock()
        self.mock_user_identity_service.find_user_by_sub = AsyncMock(return_value=None)
        self.mock_user_identity_service.create_or_swap_user = AsyncMock(
            return_value=None
        )
        self.mock_logger = MagicMock()

        # Downstream handler echoes the user_id the middleware resolved so the
        # test can assert bootstrap wrote it onto the user context.
        async def protected_endpoint(request):
            user = request.state.user
            return JSONResponse({
                "sub": user.sub,
                "user_id": user.user_id,
                "roles": list(user.roles),
            })

        async def health_check(request):
            return PlainTextResponse("OK")

        routes = [Route("/protected", protected_endpoint)]

        self.app = Starlette(routes=routes)
        self.client = TestClient(self.app)

    def _add_middleware(self):
        self.app.add_middleware(
            AuthMiddleware,
            auth_service=self.mock_auth_service,
            database=self.mock_database,
            user_identity_service=self.mock_user_identity_service,
            logger=self.mock_logger,
        )
        return TestClient(self.app)

    def test_authentication_success_find_hit(self):
        """
        Normal authenticated request: find_user_by_sub returns an existing
        user; the middleware writes user_id onto the context, never calls
        create_or_swap_user, and the request proceeds.
        """
        user_context = make_user_context(last_login_at=1700000000)
        self.mock_auth_service.authenticate_request.return_value = user_context
        self.mock_user_identity_service.find_user_by_sub.return_value = SimpleNamespace(
            user_id=42, is_active=True
        )

        client = self._add_middleware()
        response = client.get(
            "/protected", headers={"Authorization": "Bearer valid_token"}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["user_id"], 42)
        self.mock_auth_service.authenticate_request.assert_called_once()
        self.mock_user_identity_service.find_user_by_sub.assert_awaited_once_with(
            self.mock_session, "user_123", 1700000000
        )
        self.mock_user_identity_service.create_or_swap_user.assert_not_called()

    def test_first_login_creates_user(self):
        """
        First login: find_user_by_sub returns None, so create_or_swap_user is
        called and its returned user supplies the user_id.
        """
        user_context = make_user_context()
        self.mock_auth_service.authenticate_request.return_value = user_context
        self.mock_user_identity_service.find_user_by_sub.return_value = None
        self.mock_user_identity_service.create_or_swap_user.return_value = (
            SimpleNamespace(user_id=99, is_active=True)
        )

        client = self._add_middleware()
        response = client.get(
            "/protected", headers={"Authorization": "Bearer valid_token"}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["user_id"], 99)
        self.mock_user_identity_service.create_or_swap_user.assert_awaited_once_with(
            self.mock_session, user_context
        )

    def test_deactivated_user_forbidden(self):
        """
        A deactivated account authenticates (valid token, real user) but is
        barred from acting: bootstrap raises and the middleware returns 403
        without ever reaching the route handler.
        """
        user_context = make_user_context()
        self.mock_auth_service.authenticate_request.return_value = user_context
        self.mock_user_identity_service.find_user_by_sub.return_value = SimpleNamespace(
            user_id=42, is_active=False
        )

        client = self._add_middleware()
        response = client.get(
            "/protected", headers={"Authorization": "Bearer valid_token"}
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("deactivated", response.json()["message"].lower())

    def test_integrity_error_race_refinds_via_savepoint(self):
        """
        Concurrent first-login race: create_or_swap_user raises IntegrityError
        inside the savepoint; the savepoint unwinds, the outer transaction stays
        open, and the middleware re-finds the row the winner committed.
        """
        user_context = make_user_context(last_login_at=1700000000)
        self.mock_auth_service.authenticate_request.return_value = user_context

        # First find misses, second find (after the savepoint unwinds) hits.
        self.mock_user_identity_service.find_user_by_sub.side_effect = [
            None,
            SimpleNamespace(user_id=7, is_active=True),
        ]
        self.mock_user_identity_service.create_or_swap_user.side_effect = (
            IntegrityError("stmt", "params", Exception("unique"))
        )

        client = self._add_middleware()
        response = client.get(
            "/protected", headers={"Authorization": "Bearer valid_token"}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["user_id"], 7)
        # Insert was attempted inside a savepoint, no manual rollback issued.
        self.mock_session.begin_nested.assert_called_once()
        self.assertEqual(
            self.mock_user_identity_service.find_user_by_sub.await_count, 2
        )

    def test_integrity_error_not_a_race_reraises_original(self):
        """
        An IntegrityError that is NOT the race — re-find still misses, e.g. a
        primary_email already owned by another user — surfaces the original
        error instead of being masked as a retry failure.
        """
        # Both finds miss; the insert's violation is a genuine conflict.
        self.mock_user_identity_service.find_user_by_sub.side_effect = [None, None]
        self.mock_user_identity_service.create_or_swap_user.side_effect = (
            IntegrityError("stmt", "params", Exception("uq_users_primary_email"))
        )

        middleware = AuthMiddleware(
            app=MagicMock(),
            auth_service=self.mock_auth_service,
            database=self.mock_database,
            user_identity_service=self.mock_user_identity_service,
            logger=self.mock_logger,
        )
        user_context = make_user_context(last_login_at=1700000000)

        with self.assertRaises(IntegrityError):
            asyncio.run(middleware._bootstrap_user(user_context))

    def test_cron_runner_skips_bootstrap(self):
        """
        Cron / service-account tokens (identity_type "cronjob") have no
        user_identities row: bootstrap is skipped entirely (no DB session, no
        find_user_by_sub) and user_id stays None.
        """
        user_context = make_user_context(identity_type="cronjob")
        self.mock_auth_service.authenticate_request.return_value = user_context

        client = self._add_middleware()
        response = client.get(
            "/protected", headers={"Authorization": "Bearer cron_token"}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsNone(response.json()["user_id"])
        self.mock_user_identity_service.find_user_by_sub.assert_not_called()
        self.mock_user_identity_service.create_or_swap_user.assert_not_called()
        self.mock_database.session.assert_not_called()

    @patch("backend.utils.auth_middleware.api_response")
    def test_authentication_value_error(self, mock_api_response):
        """
        If AuthenticationService raises a ValueError (e.g., invalid token
        format), the middleware must return HTTPStatus.BAD_REQUEST.
        """

        def side_effect(message, status_code, data=None):
            return JSONResponse({"message": message}, status_code=status_code)

        mock_api_response.side_effect = side_effect
        self.mock_auth_service.authenticate_request.side_effect = ValueError(
            "Invalid Token Format"
        )

        client = self._add_middleware()
        response = client.get("/protected")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.json(), {"message": "Invalid Token Format"})
        mock_api_response.assert_called_with(
            message="Invalid Token Format",
            status_code=HTTPStatus.BAD_REQUEST,
            data=None,
        )

    @patch("backend.utils.auth_middleware.api_response")
    def test_authentication_general_exception(self, mock_api_response):
        """
        If AuthenticationService raises a general Exception, the middleware
        must return HTTPStatus.FORBIDDEN with "Authentication failed".
        """

        def side_effect(message, status_code, data=None):
            return JSONResponse({"message": message}, status_code=status_code)

        mock_api_response.side_effect = side_effect
        self.mock_auth_service.authenticate_request.side_effect = Exception(
            "Unexpected Error"
        )

        client = self._add_middleware()
        response = client.get("/protected")

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(response.json(), {"message": "Authentication failed"})
        mock_api_response.assert_called_with(
            message="Authentication failed", status_code=HTTPStatus.FORBIDDEN, data=None
        )

    def test_dispatch_offloads_authenticate_to_thread(self):
        """
        The middleware must run authenticate_request through asyncio.to_thread
        so any blocking sync work (e.g. JWKS refresh) does not block the event
        loop. Asserted via a wrapping spy so a regression to a direct sync call
        is caught in CI.
        """
        user_context = make_user_context()
        self.mock_auth_service.authenticate_request.return_value = user_context
        self.mock_user_identity_service.find_user_by_sub.return_value = SimpleNamespace(
            user_id=1, is_active=True
        )

        client = self._add_middleware()

        with patch(
            "backend.utils.auth_middleware.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as spy_to_thread:
            response = client.get(
                "/protected", headers={"Authorization": "Bearer valid_token"}
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        matching = [
            c
            for c in spy_to_thread.call_args_list
            if c.args and c.args[0] is self.mock_auth_service.authenticate_request
        ]
        self.assertEqual(len(matching), 1)


if __name__ == "__main__":
    unittest.main()
