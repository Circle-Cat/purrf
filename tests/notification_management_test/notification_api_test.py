from http import HTTPStatus
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import patch, AsyncMock
from flask import Flask, jsonify
from src.notification_management.notification_api import notification_bp
from src.common.constants import MicrosoftAccountStatus, EVENT_TYPES
import json
import asyncio

SUBSCRIBE_MICROSOFT_CHAT_MESSAGES_API = "/api/microsoft/chat/subscribe"


class TestNotificationApi(IsolatedAsyncioTestCase):
    @classmethod
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(notification_bp)
        self.client = app.test_client()
        app.testing = True

    @patch(
        "src.notification_management.notification_api.subscribe_chat_messages",
        new_callable=AsyncMock,
    )
    async def test_subscribe_success(self, mock_subscribe):
        """Test the /api/microsoft/chat/subscribe endpoint for a successful subscription."""
        mock_subscribe.return_value = (
            "Subscription created successfully for chat_id 19:meeting_ID@thread.skype.",
            {
                "expiration_timestamp": "2025-05-27T12:34:56.000Z",
                "chat_id": "19:meeting_ID@thread.skype",
                "subscription_id": "abc123",
            },
        )
        payload = {
            "chat_id": "19:meeting_ID@thread.skype",
            "notification_url": "https://example.com/notifications",
            "lifecycle_notification_url": "https://example.com/lifecycle",
        }

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.post(
                SUBSCRIBE_MICROSOFT_CHAT_MESSAGES_API,
                data=json.dumps(payload),
                content_type="application/json",
            ),
        )
        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        data = response.get_json()
        self.assertEqual(data["message"], mock_subscribe.return_value[0])
        self.assertEqual(data["data"], mock_subscribe.return_value[1])

    async def test_subscribe_missing_param(self):
        """Test the /api/microsoft/chat/subscribe endpoint for missing required parameter lifecycle_notification_url."""
        payload = {
            "chat_id": "19:meeting_ID@thread.skype",
            "notification_url": "https://example.com/notifications",
        }

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.client.post(
                    SUBSCRIBE_MICROSOFT_CHAT_MESSAGES_API,
                    data=json.dumps(payload),
                    content_type="application/json",
                ),
            )
        except ValueError as e:
            self.assertIn("lifecycle_notification_url", str(e))

    @patch(
        "src.notification_management.notification_api.create_workspaces_subscriptions"
    )
    def test_subscribe_success(self, mock_create_subscription):
        payload = {
            "project_id": "test-project",
            "topic_id": "test-topic",
            "space_id": "test-space",
            "event_types": list(EVENT_TYPES),
        }

        mock_create_subscription.return_value = {"subscription_id": "mock-subscription"}

        response = self.client.post(
            "/api/google/chat/spaces/subscribe",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        data = response.get_json()
        self.assertEqual(data["message"]["subscription_id"], "mock-subscription")

        mock_create_subscription.assert_called_once_with(
            payload["project_id"],
            payload["topic_id"],
            payload["space_id"],
            set(payload["event_types"]),
        )


if __name__ == "__main__":
    main()
