import unittest
from unittest.mock import MagicMock, patch
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from http import HTTPStatus
from backend.utils.auth_middleware import AuthMiddleware


class TestAuthMiddleware(unittest.TestCase):
    def setUp(self):
        """
        Runs before each test.

        Initializes a Starlette application containing test routes,
        and prepares a mocked AuthenticationService instance.
        """
        self.mock_auth_service = MagicMock()

        # Define test routes simulating downstream handlers
        async def protected_endpoint(request):
            # Return the user injected into request.state.user
            return JSONResponse({"user": request.state.user})

        async def health_check(request):
            return PlainTextResponse("OK")

        routes = [Route("/protected", protected_endpoint)]

        # Initialize the app
        self.app = Starlette(routes=routes)
        self.client = TestClient(self.app)

    @patch("backend.utils.auth_middleware.api_response")
    def test_authentication_success(self, mock_api_response):
        """
        Test: When authentication succeeds, the middleware must inject
        the user context into request.state.user and allow the request to continue.
        """
        expected_user_context = {
            "sub": "user_123",
            "primary_email": "test@example.com",
            "roles": ["admin"],
        }
        self.mock_auth_service.authenticate_request.return_value = expected_user_context

        self.app.add_middleware(AuthMiddleware, auth_service=self.mock_auth_service)
        client = TestClient(self.app)

        response = client.get(
            "/protected", headers={"Authorization": "Bearer valid_token"}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json(), {"user": expected_user_context})
        self.mock_auth_service.authenticate_request.assert_called_once()

    @patch("backend.utils.auth_middleware.api_response")
    def test_authentication_value_error(self, mock_api_response):
        """
        Test: If AuthenticationService raises a ValueError
        (e.g., invalid token format), the middleware must return
        HTTPStatus.BAD_REQUEST.
        """

        # Mock api_response to return JSONResponse
        def side_effect(message, status_code, data=None):
            return JSONResponse({"message": message}, status_code=status_code)

        mock_api_response.side_effect = side_effect

        # Simulate ValueError thrown by authentication service
        self.mock_auth_service.authenticate_request.side_effect = ValueError(
            "Invalid Token Format"
        )

        self.app.add_middleware(AuthMiddleware, auth_service=self.mock_auth_service)
        client = TestClient(self.app)

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
        Test: If AuthenticationService raises a general Exception,
        the middleware must return HTTPStatus.FORBIDDEN with the message
        "Authentication failed".
        """

        def side_effect(message, status_code, data=None):
            return JSONResponse({"message": message}, status_code=status_code)

        mock_api_response.side_effect = side_effect

        # Simulate general exception
        self.mock_auth_service.authenticate_request.side_effect = Exception(
            "Unexpected Error"
        )

        self.app.add_middleware(AuthMiddleware, auth_service=self.mock_auth_service)
        client = TestClient(self.app)

        response = client.get("/protected")

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(response.json(), {"message": "Authentication failed"})

        mock_api_response.assert_called_with(
            message="Authentication failed", status_code=HTTPStatus.FORBIDDEN, data=None
        )


if __name__ == "__main__":
    unittest.main()
