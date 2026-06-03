import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from backend.common.api_endpoints import MY_PERMISSIONS
from backend.common.identity_type import IdentityType
from backend.common.permissions import Permission
from backend.authentication.authentication_controller import AuthenticationController
from http import HTTPStatus


class _FakeSessionContext:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


class TestAuthenticationController(unittest.TestCase):
    def setUp(self):
        """
        Initialize the test environment.
        """
        self.user_emails_repository = AsyncMock()
        self.user_emails_repository.has_confirmed.return_value = False
        database = MagicMock()
        database.session.return_value = _FakeSessionContext()
        self.controller = AuthenticationController(
            user_emails_repository=self.user_emails_repository,
            database=database,
        )

        # Create a temporary FastAPI app to attach the controller's router
        self.app = FastAPI()
        self.app.include_router(self.controller.router)

        # Patch api_response
        # This step is critical: we need api_response to return a real JSONResponse
        # instead of a Mock object, otherwise TestClient cannot parse the response.
        self.patcher = patch(
            "backend.authentication.authentication_controller.api_response"
        )
        self.mock_api_response = self.patcher.start()

        # Mock the real behavior of api_response (returning JSONResponse)
        def side_effect(data, message, status_code=HTTPStatus.OK):
            return JSONResponse(
                content={"message": message, "data": data}, status_code=status_code
            )

        self.mock_api_response.side_effect = side_effect

    def tearDown(self):
        """
        Stop all patches.
        """
        self.patcher.stop()

    def _get_client_with_mock_user(
        self,
        permissions,
        sub="test-sub",
        email="test@example.com",
        is_super_admin=False,
        user_id=42,
        identity_type=IdentityType.INTERNAL,
    ):
        """
        Helper method:
        Create a TestClient and inject a fake user into request.state before handling the request.
        @authenticate decorator reads the user context from request.state.user to perform
        authorization and argument injection.
        """
        mock_user = MagicMock()
        mock_user.permissions = frozenset(permissions)
        mock_user.sub = sub
        mock_user.primary_email = email
        mock_user.is_super_admin = is_super_admin
        mock_user.user_id = user_id
        mock_user.identity_type = identity_type

        @self.app.middleware("http")
        async def mock_auth_middleware(request: Request, call_next):
            request.state.user = mock_user
            return await call_next(request)

        return TestClient(self.app)

    def test_get_my_permissions_success(self):
        """
        Test: successfully retrieving user permissions.
        """
        expected_sub = "user-123"
        expected_email = "user@test.com"
        self.user_emails_repository.has_confirmed.return_value = True

        client = self._get_client_with_mock_user(
            permissions={Permission.INTERNAL_ACTIVITY_READ},
            sub=expected_sub,
            email=expected_email,
            is_super_admin=False,
            user_id=42,
        )

        response = client.get(MY_PERMISSIONS)

        self.assertEqual(response.status_code, HTTPStatus.OK)

        json_resp = response.json()
        self.assertEqual(json_resp["data"]["permissions"], ["internal_activity.read"])
        self.assertEqual(json_resp["data"]["sub"], expected_sub)
        self.assertEqual(json_resp["data"]["user_id"], 42)
        self.assertEqual(json_resp["data"]["email"], expected_email)
        self.assertEqual(json_resp["data"]["identity_type"], "internal")
        self.assertTrue(json_resp["data"]["has_verified_email"])
        self.assertFalse(json_resp["data"]["is_super_admin"])

        self.mock_api_response.assert_called_once()

    def test_get_my_permissions_empty(self):
        """
        Test: behavior when the user has no permissions.
        """
        client = self._get_client_with_mock_user(permissions=frozenset())

        response = client.get(MY_PERMISSIONS)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"]["permissions"], [])

    def test_get_my_permissions_missing_user_context(self):
        """
        Test: behavior when current_user is not provided.
        Authenticate decorator should intercept the request with 401 Unauthorized.
        """
        client = TestClient(self.app, raise_server_exceptions=False)
        response = client.get(MY_PERMISSIONS)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
