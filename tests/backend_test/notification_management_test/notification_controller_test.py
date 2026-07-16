import unittest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from http import HTTPStatus

from backend.common.permissions import Permission
from backend.common.api_endpoints import (
    GOOGLE_CHAT_SUBSCRIBE_ENDPOINT,
    MICROSOFT_CHAT_SUBSCRIBE_ENDPOINT,
)
from backend.utils.auth_middleware import AuthMiddleware
from backend.notification_management.notification_controller import (
    NotificationController,
)


class TestNotificationIntegration(unittest.TestCase):
    def setUp(self):
        # Mock the authentication service (dependency of the middleware)
        self.mock_auth_service = MagicMock()

        # Mock the business services (we only test the web integration layer)
        self.microsoft_service = AsyncMock()
        self.google_service = MagicMock()

        # Initialize the controller
        self.controller = NotificationController(
            microsoft_chat_subscription_service=self.microsoft_service,
            google_chat_subscription_service=self.google_service,
        )

        # Mock async DB session + user identity service for middleware bootstrap
        mock_session = MagicMock()
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        begin_cm = MagicMock()
        begin_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        begin_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=begin_cm)
        self.mock_database = MagicMock()
        self.mock_database.session = MagicMock(return_value=session_cm)
        self.mock_user_identity_service = MagicMock()
        self.mock_user_identity_service.find_user_by_sub = AsyncMock(
            return_value=MagicMock(user_id=1, is_super_admin=False)
        )
        self.mock_user_permissions_repository = MagicMock()
        self.mock_user_permissions_repository.get_active_permission_names = AsyncMock(
            return_value=[]
        )

        # Assemble the FastAPI app
        self.app = FastAPI()

        # Add the real authentication middleware
        self.app.add_middleware(
            AuthMiddleware,
            auth_service=self.mock_auth_service,
            database=self.mock_database,
            user_identity_service=self.mock_user_identity_service,
            user_permissions_repository=self.mock_user_permissions_repository,
            logger=MagicMock(),
        )

        # Include routes from the controller
        self.app.include_router(self.controller.router)

        self.client = TestClient(self.app)

    def _set_authenticated_user(self, permissions=None, sub="test_user_123"):
        """Resolve the request user to the given permissions via the middleware."""
        if permissions is None:
            permissions = [Permission.SYSTEM_SUBSCRIBE]

        mock_user = MagicMock()
        mock_user.sub = sub
        mock_user.is_service_account = False
        mock_user.is_super_admin = False
        mock_user.primary_email = "admin@example.com"

        # Return this user when authenticate_request is called by the middleware
        self.mock_auth_service.authenticate_request.return_value = mock_user
        self.mock_user_permissions_repository.get_active_permission_names.return_value = [
            p.value for p in permissions
        ]

    def test_microsoft_subscribe_integration_success(self):
        """Verify the full flow from auth to Microsoft subscription"""

        # Configure auth service: simulate a user holding the subscribe permission
        self._set_authenticated_user(permissions=[Permission.SYSTEM_SUBSCRIBE])

        # Configure business service return value
        self.microsoft_service.subscribe_chat_messages.return_value = (
            "Successfully created",
            {"id": "sub_001"},
        )

        payload = {
            "chat_id": "19:meeting@thread.skype",
            "notification_url": "https://callback.com",
            "lifecycle_notification_url": "https://lifecycle.com",
        }

        # Send request with any Authorization header to trigger middleware logic
        response = self.client.post(
            MICROSOFT_CHAT_SUBSCRIBE_ENDPOINT,
            json=payload,
            headers={"Authorization": "Bearer mock-token"},
        )

        # Verify result
        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertTrue(response.json()["success"])
        # Verify middleware was called correctly
        self.mock_auth_service.authenticate_request.assert_called_once()

    def test_google_subscribe_integration_forbidden(self):
        """Verify middleware/decorator blocks when roles do not match"""

        # Configure auth service: simulate a user without the subscribe permission
        self._set_authenticated_user(permissions=[])

        payload = {"project_id": "p1", "topic_id": "t1", "space_id": "s1"}

        response = self.client.post(
            GOOGLE_CHAT_SUBSCRIBE_ENDPOINT,
            json=payload,
            headers={"Authorization": "Bearer mock-token"},
        )

        # Verify it is blocked: should return 403 Forbidden (from decorator)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertFalse(response.json()["success"])
        # Verify business service was never called
        self.google_service.create_workspaces_subscriptions.assert_not_called()

    def test_auth_failure_integration(self):
        """Verify middleware behavior when token is invalid"""

        # Configure auth service to raise ValueError (simulate token validation failure)
        self.mock_auth_service.authenticate_request.side_effect = ValueError(
            "Invalid token"
        )

        response = self.client.post(
            GOOGLE_CHAT_SUBSCRIBE_ENDPOINT,
            json={},
            headers={"Authorization": "Bearer invalid-token"},
        )

        # Verify middleware returns 400 Bad Request (as defined in middleware logic)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.json()["message"], "Invalid token")


if __name__ == "__main__":
    unittest.main()
