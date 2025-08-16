from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from backend.notification_management.microsoft_chat_subscription_service import (
    MicrosoftChatSubscriptionService,
)
from backend.common.constants import (
    MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE,
    MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY,
    MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_CLIENT_STATE_BYTE_LENGTH,
    MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_MAX_LIFETIME,
)


class TestMicrosoftChatSubscriptionService(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.chat_id = "19:meeting_ID@thread.skype"
        self.notification_url = "https://example.com/notifications"
        self.lifecycle_url = "https://example.com/lifecycle"
        self.current_time = datetime.now(timezone.utc)
        self.sub_id = "new123"
        self.legacy_id = "old456"
        self.client_state = "securetoken123"
        self.valid_subscription = MagicMock(
            resource=MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE.format(
                chat_id=self.chat_id
            ),
            expiration_date_time=self.current_time + timedelta(hours=1),
            change_type="created,updated,deleted",
            notification_url=self.notification_url,
            lifecycle_notification_url=self.lifecycle_url,
            id=self.sub_id,
        )
        self.expired_subscription = MagicMock(
            resource=MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE.format(
                chat_id=self.chat_id
            ),
            expiration_date_time=self.current_time - timedelta(hours=1),
            change_type="created,updated,deleted",
            notification_url=self.notification_url,
            lifecycle_notification_url=self.lifecycle_url,
            id=self.legacy_id,
        )
        self.logger = MagicMock()
        self.redis_client = MagicMock()
        self.microsoft_service = AsyncMock()
        self.service = MicrosoftChatSubscriptionService(
            logger=self.logger,
            redis_client=self.redis_client,
            microsoft_service=self.microsoft_service,
        )

    @patch.object(MicrosoftChatSubscriptionService, "_generate_client_state")
    @patch.object(MicrosoftChatSubscriptionService, "_update_client_state")
    async def test_successful_new_subscription(
        self, mock_update_client_state, mock_generate_client_state
    ):
        mock_generate_client_state.return_value = self.client_state
        self.microsoft_service.list_all_subscriptions.return_value = []
        created_sub = MagicMock(
            id="new_sub123", expiration_date_time=self.current_time + timedelta(days=3)
        )
        self.microsoft_service.create_subscription = AsyncMock(return_value=created_sub)
        _, info = await self.service.subscribe_chat_messages(
            self.chat_id, self.notification_url, self.lifecycle_url
        )
        self.assertIn("subscription_id", info)
        self.assertEqual(info["chat_id"], self.chat_id)
        self.microsoft_service.list_all_subscriptions.assert_awaited_once()
        self.microsoft_service.create_subscription.assert_awaited_once()
        mock_generate_client_state.assert_called_once()
        mock_update_client_state.assert_called_once_with(
            created_sub.id, self.client_state, None
        )

    @patch.object(MicrosoftChatSubscriptionService, "_generate_client_state")
    @patch.object(MicrosoftChatSubscriptionService, "_update_client_state")
    async def test_existing_valid_subscription(
        self, mock_update_client_state, mock_generate_client_state
    ):
        self.microsoft_service.list_all_subscriptions.return_value = [
            self.valid_subscription
        ]
        _, info = await self.service.subscribe_chat_messages(
            self.chat_id, self.notification_url, self.lifecycle_url
        )
        self.assertEqual(info["subscription_id"], self.valid_subscription.id)
        self.microsoft_service.list_all_subscriptions.assert_awaited_once()
        self.microsoft_service.create_subscription.assert_not_called()
        mock_update_client_state.assert_not_called()
        mock_generate_client_state.assert_not_called()

    @patch.object(MicrosoftChatSubscriptionService, "_generate_client_state")
    @patch.object(MicrosoftChatSubscriptionService, "_update_client_state")
    async def test_delete_existing_and_create_new_subscription(
        self, mock_update_client_state, mock_generate_client_state
    ):
        mock_generate_client_state.return_value = self.client_state
        different_change_sub = MagicMock(
            resource=MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE.format(
                chat_id=self.chat_id
            ),
            expiration_date_time=self.current_time + timedelta(hours=1),
            change_type="created",
            notification_url=self.notification_url,
            lifecycle_notification_url=self.lifecycle_url,
            id=self.legacy_id,
        )
        self.microsoft_service.list_all_subscriptions.return_value = [
            different_change_sub
        ]
        delete_mock = AsyncMock()
        self.microsoft_service.delete_subscription = delete_mock
        expiration_dt = self.current_time + timedelta(
            minutes=MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_MAX_LIFETIME
        )
        created_sub = MagicMock(id="new_sub123", expiration_date_time=expiration_dt)
        self.microsoft_service.create_subscription = AsyncMock(return_value=created_sub)
        message, info = await self.service.subscribe_chat_messages(
            self.chat_id, self.notification_url, self.lifecycle_url
        )
        self.assertEqual(
            message, f"Subscription created successfully for chat_id {self.chat_id}."
        )
        self.assertIn("subscription_id", info)
        self.microsoft_service.list_all_subscriptions.assert_awaited_once()
        delete_mock.assert_awaited_once_with(different_change_sub.id)
        self.microsoft_service.create_subscription.assert_awaited_once()
        mock_generate_client_state.assert_called_once()
        mock_update_client_state.assert_called_once_with(
            created_sub.id, self.client_state, different_change_sub.id
        )

    async def test_missing_required_parameters(self):
        with self.assertRaises(ValueError) as cm:
            await self.service.subscribe_chat_messages(
                "", self.notification_url, self.lifecycle_url
            )
        self.assertIn("chat_id", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            await self.service.subscribe_chat_messages(
                self.chat_id, "", self.lifecycle_url
            )
        self.assertIn("notification_url", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            await self.service.subscribe_chat_messages(
                self.chat_id, self.notification_url, ""
            )
        self.assertIn("lifecycle_notification_url", str(cm.exception))

    def test_generate_client_state_length_and_uniqueness(self):
        client_state1 = self.service._generate_client_state()
        client_state2 = self.service._generate_client_state()
        self.assertIsInstance(client_state1, str)
        self.assertGreaterEqual(
            len(client_state1.encode("utf-8")),
            MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_CLIENT_STATE_BYTE_LENGTH,
        )
        self.assertNotEqual(client_state1, client_state2)

    def test_update_client_state_successful(self):
        pipeline_mock = MagicMock()
        self.redis_client.pipeline.return_value = pipeline_mock
        pipeline_mock.execute.return_value = True
        try:
            self.service._update_client_state(
                self.sub_id, self.client_state, self.legacy_id
            )
        except Exception:
            self.fail("_update_client_state raised unexpectedly!")
        pipeline_mock.set.assert_called_once_with(
            MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY.format(
                subscription_id=self.sub_id
            ),
            self.client_state,
        )
        pipeline_mock.delete.assert_called_once_with(
            MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY.format(
                subscription_id=self.legacy_id
            )
        )
        pipeline_mock.execute.assert_called_once()

    def test_update_client_state_missing_params(self):
        with self.assertRaises(ValueError):
            self.service._update_client_state("", "abc", None)
        with self.assertRaises(ValueError):
            self.service._update_client_state("abc", "", None)

    def test_update_client_state_pipeline_execute_fails(self):
        pipeline_mock = MagicMock()
        self.redis_client.pipeline.return_value = pipeline_mock
        pipeline_mock.execute.side_effect = RuntimeError("Redis failure")
        with self.assertRaises(RuntimeError) as cm:
            self.service._update_client_state(
                self.sub_id, self.client_state, self.legacy_id
            )
        self.assertIn("Failed to update the client_state", str(cm.exception))


if __name__ == "__main__":
    main()
