import asyncio
import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from http import HTTPStatus

from backend.common.api_endpoints import PUBSUB_SYNC_PULL_ENDPOINT
from backend.common.permissions import Permission
from backend.dto.user_context_dto import UserContextDto
from backend.consumers.consumer_controller import ConsumerController


class TestConsumerController(unittest.TestCase):
    def setUp(self):
        self.mock_sync_pull_service = MagicMock()
        self.controller = ConsumerController(
            pubsub_sync_pull_service=self.mock_sync_pull_service,
        )
        self.app = FastAPI()
        self.app.include_router(self.controller.router)

    def _client(self, permissions):
        """TestClient that injects a user holding `permissions` as request.state.user."""
        user = UserContextDto(
            sub="test_user",
            primary_email="test@example.com",
            permissions=frozenset(permissions),
        )

        @self.app.middleware("http")
        async def _inject_user(request: Request, call_next):
            request.state.user = user
            return await call_next(request)

        return TestClient(self.app)

    def test_sync_pull_all_success(self):
        client = self._client([Permission.SYSTEM_SYNC])
        self.mock_sync_pull_service.sync_pull_all.return_value = {
            "microsoft": {"processed": 5, "failed": 0},
            "google_chat": {"processed": 3, "failed": 0},
            "gerrit": {"processed": 10, "failed": 1},
        }

        response = client.post(
            PUBSUB_SYNC_PULL_ENDPOINT,
            headers={"Authorization": "Bearer valid-token"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.json()["success"])
        self.mock_sync_pull_service.sync_pull_all.assert_called_once()

    def test_sync_pull_offloads_to_thread(self):
        """
        The controller must run pubsub_sync_pull_service.sync_pull_all
        through asyncio.to_thread so its long synchronous loop (up to
        50 minutes) does not block the event loop. We assert via a
        wrapping spy on asyncio.to_thread.
        """
        client = self._client([Permission.SYSTEM_SYNC])
        self.mock_sync_pull_service.sync_pull_all.return_value = {
            "microsoft": {"processed": 0, "failed": 0},
        }

        with patch(
            "backend.consumers.consumer_controller.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as spy_to_thread:
            response = client.post(
                PUBSUB_SYNC_PULL_ENDPOINT,
                headers={"Authorization": "Bearer valid-token"},
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        matching = [
            c
            for c in spy_to_thread.call_args_list
            if c.args and c.args[0] is self.mock_sync_pull_service.sync_pull_all
        ]
        self.assertEqual(len(matching), 1)

    def test_sync_pull_forbidden_for_normal_user(self):
        client = self._client([])

        response = client.post(
            PUBSUB_SYNC_PULL_ENDPOINT,
            headers={"Authorization": "Bearer valid-token"},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.mock_sync_pull_service.sync_pull_all.assert_not_called()


if __name__ == "__main__":
    unittest.main()
