import json
from http import HTTPStatus

from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock
from flask import Flask

from backend.notification_management.notification_controller import (
    NotificationController,
)
from backend.common.constants import SINGLE_GOOGLE_CHAT_EVENT_TYPES


class TestNotificationController(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.microsoft_chat_subscription_service = AsyncMock()
        self.google_chat_subscription_service = MagicMock()
        self.controller = NotificationController(
            microsoft_chat_subscription_service=self.microsoft_chat_subscription_service,
            google_chat_subscription_service=self.google_chat_subscription_service,
        )

        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

    async def asyncTearDown(self):
        self.app_context.pop()

    async def test_subscribe_microsoft_chat_messages_success(self):
        mock_return_value = (
            "Subscription created successfully for chat_id 19:meeting_ID@thread.skype.",
            {
                "expiration_timestamp": "2025-05-27T12:34:56.000Z",
                "chat_id": "19:meeting_ID@thread.skype",
                "subscription_id": "abc123",
            },
        )
        self.microsoft_chat_subscription_service.subscribe_chat_messages.return_value = mock_return_value

        payload = {
            "chat_id": "19:meeting_ID@thread.skype",
            "notification_url": "https://example.com/notifications",
            "lifecycle_notification_url": "https://example.com/lifecycle",
        }

        with self.app.test_request_context(
            "/microsoft/chat/subscribe",
            method="POST",
            data=json.dumps(payload),
            content_type="application/json",
        ):
            response = await self.controller.subscribe_microsoft_chat_messages()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(response.json["message"], mock_return_value[0])
        self.assertEqual(response.json["data"], mock_return_value[1])

    def test_subscribe_google_chat_messages_success(self):
        self.google_chat_subscription_service.create_workspaces_subscriptions.return_value = {
            "subscription_id": "mock-subscription"
        }
        payload = {
            "project_id": "test-project",
            "topic_id": "test-topic",
            "space_id": "test-space",
        }

        with self.app.test_request_context(
            "/google/chat/spaces/subscribe",
            method="POST",
            data=json.dumps(payload),
            content_type="application/json",
        ):
            response = self.controller.subscribe_google_chat_space()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(
            response.json["message"]["subscription_id"], "mock-subscription"
        )

        self.google_chat_subscription_service.create_workspaces_subscriptions.assert_called_once_with(
            project_id=payload["project_id"],
            topic_id=payload["topic_id"],
            space_id=payload["space_id"],
            event_types=SINGLE_GOOGLE_CHAT_EVENT_TYPES,
        )


if __name__ == "__main__":
    main()
