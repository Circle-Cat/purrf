import unittest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from http import HTTPStatus

from backend.common.api_endpoints import PUBSUB_SYNC_PULL_ENDPOINT
from backend.common.user_role import UserRole
from backend.utils.auth_middleware import AuthMiddleware
from backend.consumers.consumer_controller import ConsumerController


class TestConsumerController(unittest.TestCase):
    def setUp(self):
        self.mock_auth_service = MagicMock()
        self.mock_sync_pull_service = MagicMock()

        self.controller = ConsumerController(
            pubsub_sync_pull_service=self.mock_sync_pull_service,
        )

        self.app = FastAPI()
        self.app.add_middleware(AuthMiddleware, auth_service=self.mock_auth_service)
        self.app.include_router(self.controller.router)
        self.client = TestClient(self.app)

    def _set_authenticated_user(self, roles=None):
        if roles is None:
            roles = [UserRole.INFRA_ADMIN]
        mock_user = MagicMock()
        mock_user.sub = "test_user"
        mock_user.roles = roles
        mock_user.primary_email = "test@example.com"
        self.mock_auth_service.authenticate_request.return_value = mock_user

    def test_sync_pull_all_success(self):
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])
        self.mock_sync_pull_service.sync_pull_all.return_value = {
            "microsoft": {"processed": 5, "failed": 0},
            "google_chat": {"processed": 3, "failed": 0},
            "gerrit": {"processed": 10, "failed": 1},
        }

        response = self.client.post(
            PUBSUB_SYNC_PULL_ENDPOINT,
            headers={"Authorization": "Bearer valid-token"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.json()["success"])
        self.mock_sync_pull_service.sync_pull_all.assert_called_once()

    def test_sync_pull_forbidden_for_normal_user(self):
        self._set_authenticated_user(roles=[UserRole.MENTORSHIP])

        response = self.client.post(
            PUBSUB_SYNC_PULL_ENDPOINT,
            headers={"Authorization": "Bearer valid-token"},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.mock_sync_pull_service.sync_pull_all.assert_not_called()


if __name__ == "__main__":
    unittest.main()
