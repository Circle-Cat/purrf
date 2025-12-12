import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from backend.common.api_endpoints import MY_ROLES
from backend.authentication.authentication_controller import AuthenticationController
from http import HTTPStatus


class TestAuthenticationController(unittest.TestCase):
    def setUp(self):
        """
        Initialize the test environment.
        """
        self.controller = AuthenticationController()

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

    def _get_client_with_mock_user(self, roles):
        """
        Helper method:
        Create a TestClient and inject a fake user into request.state before handling the request.
        """
        mock_user = MagicMock()
        mock_user.roles = roles

        @self.app.middleware("http")
        async def mock_auth_middleware(request: Request, call_next):
            request.state.user = mock_user
            return await call_next(request)

        return TestClient(self.app)

    def test_get_my_roles_success(self):
        """
        Test: successfully retrieving user roles.
        """
        expected_roles = ["admin", "cc_internal"]

        client = self._get_client_with_mock_user(roles=expected_roles)
        response = client.get(MY_ROLES)

        self.assertEqual(response.status_code, HTTPStatus.OK)

        json_resp = response.json()
        self.assertEqual(json_resp["message"], "Successfully")
        self.assertEqual(json_resp["data"]["roles"], expected_roles)
        self.mock_api_response.assert_called_once()

    def test_get_my_roles_empty(self):
        """
        Test: behavior when the user has no roles.
        """
        expected_roles = []
        client = self._get_client_with_mock_user(roles=expected_roles)

        response = client.get(MY_ROLES)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"]["roles"], [])

    def test_get_my_roles_missing_user_state(self):
        """
        Test: request.state.user is missing
        (e.g., authentication middleware failed or is not applied).
        """
        client = TestClient(self.app, raise_server_exceptions=False)
        response = client.get(MY_ROLES)

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)


if __name__ == "__main__":
    unittest.main()
