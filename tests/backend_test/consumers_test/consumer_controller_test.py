import unittest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from http import HTTPStatus

from backend.common.user_role import UserRole
from backend.common.api_endpoints import (
    MICROSOFT_PULL_ENDPOINT,
    GOOGLE_CHAT_PULL_ENDPOINT,
    GERRIT_PULL_ENDPOINT,
    PUBSUB_STATUS_ENDPOINT,
    PUBSUB_STOP_ENDPOINT,
)
from backend.utils.auth_middleware import AuthMiddleware
from backend.consumers.consumer_controller import ConsumerController


class TestConsumerIntegration(unittest.TestCase):
    def setUp(self):
        # 1. Mock authentication service
        self.mock_auth_service = MagicMock()

        # 2. Mock business services (four dependencies required by the controller)
        self.mock_ms_service = MagicMock()
        self.mock_google_service = MagicMock()
        self.mock_gerrit_service = MagicMock()
        self.mock_pull_manager = MagicMock()

        # 3. Initialize controller
        self.controller = ConsumerController(
            microsoft_message_processor_service=self.mock_ms_service,
            google_chat_processor_service=self.mock_google_service,
            gerrit_processor_service=self.mock_gerrit_service,
            pubsub_pull_manager=self.mock_pull_manager,
        )

        # 4. Build FastAPI app
        self.app = FastAPI()
        self.app.add_middleware(AuthMiddleware, auth_service=self.mock_auth_service)
        self.app.include_router(self.controller.router)

        self.client = TestClient(self.app)

        # Test constants
        self.project_id = "test-project"
        self.sub_id = "test-subscription"

    def _set_authenticated_user(self, roles=None, sub="test_user_123"):
        """Helper method to configure mock_auth_service to return a user with given roles."""
        if roles is None:
            roles = [UserRole.ADMIN]
        mock_user = MagicMock()
        mock_user.sub = sub
        mock_user.roles = roles
        mock_user.primary_email = "test@example.com"
        self.mock_auth_service.authenticate_request.return_value = mock_user

    def _get_url(self, endpoint_template):
        """Helper method to replace {project_id} and {subscription_id} in endpoint templates."""
        return endpoint_template.format(
            project_id=self.project_id, subscription_id=self.sub_id
        )

    def test_start_google_chat_pulling_success(self):
        """Test Google Chat pull endpoint with ADMIN role."""
        self._set_authenticated_user(roles=[UserRole.ADMIN])

        url = self._get_url(GOOGLE_CHAT_PULL_ENDPOINT)
        response = self.client.post(
            url, headers={"Authorization": "Bearer valid-token"}
        )

        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)
        self.assertTrue(response.json()["success"])
        self.mock_google_service.pull_messages.assert_called_once_with(
            self.project_id, self.sub_id
        )

    def test_start_microsoft_pulling_success(self):
        """Test Microsoft pull endpoint with ADMIN role."""
        self._set_authenticated_user(roles=[UserRole.ADMIN])

        url = self._get_url(MICROSOFT_PULL_ENDPOINT)
        response = self.client.post(
            url, headers={"Authorization": "Bearer valid-token"}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue("Microsoft" in response.json()["message"])
        self.mock_ms_service.pull_microsoft_message.assert_called_once_with(
            self.project_id, self.sub_id
        )

    def test_check_pulling_status_success(self):
        """Test check pulling status endpoint with ADMIN role."""
        self._set_authenticated_user(roles=[UserRole.ADMIN])

        self.mock_pull_manager.check_pulling_status.return_value = {"status": "running"}

        url = self._get_url(PUBSUB_STATUS_ENDPOINT)
        response = self.client.get(url, headers={"Authorization": "Bearer valid-token"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"]["status"], "running")
        self.mock_pull_manager.check_pulling_status.assert_called_once()

    def test_stop_pulling_success(self):
        """Test stop pulling endpoint using DELETE method."""
        self._set_authenticated_user(roles=[UserRole.ADMIN])

        self.mock_pull_manager.stop_pulling_process.return_value = {"stopped": True}

        url = self._get_url(PUBSUB_STOP_ENDPOINT)
        response = self.client.delete(
            url, headers={"Authorization": "Bearer valid-token"}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.json()["success"])
        self.mock_pull_manager.stop_pulling_process.assert_called_once()

    def test_forbidden_access_for_normal_user(self):
        """Test forbidden access: normal user tries to access ADMIN endpoint."""
        # Simulate a normal user without ADMIN role
        self._set_authenticated_user(roles=[UserRole.MENTORSHIP])

        url = self._get_url(PUBSUB_STOP_ENDPOINT)
        response = self.client.delete(
            url, headers={"Authorization": "Bearer valid-token"}
        )

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        # Business logic should not be invoked
        self.mock_pull_manager.stop_pulling_process.assert_not_called()

    def test_auth_token_invalid(self):
        """Test invalid authentication token."""
        self.mock_auth_service.authenticate_request.side_effect = ValueError(
            "Invalid token"
        )

        url = self._get_url(GERRIT_PULL_ENDPOINT)
        response = self.client.post(url, headers={"Authorization": "Bearer bad-token"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.json()["message"], "Invalid token")


if __name__ == "__main__":
    unittest.main()
