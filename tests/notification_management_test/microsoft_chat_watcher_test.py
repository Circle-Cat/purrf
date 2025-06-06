from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from src.notification_management.microsoft_chat_watcher import (
    subscribe_chat_messages,
    _generate_client_state,
    _update_client_state,
)
from src.common.constants import (
    MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE,
    MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY,
    MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_CLIENT_STATE_BYTE_LENGTH,
)


class TestSubscribeChatMessages(IsolatedAsyncioTestCase):
    def setUp(self):
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

    @patch("src.notification_management.microsoft_chat_watcher._generate_client_state")
    @patch("src.notification_management.microsoft_chat_watcher._update_client_state")
    @patch("src.notification_management.microsoft_chat_watcher.datetime")
    @patch("src.notification_management.microsoft_chat_watcher.MicrosoftClientFactory")
    async def test_successful_new_subscription(
        self,
        mock_ms_factory,
        mock_datetime,
        mock_update_client_state,
        mock_generate_client_state,
    ):
        """Test creating a new subscription when none exists"""
        mock_datetime.now.return_value = self.current_time
        mock_client = AsyncMock()
        mock_ms_factory.return_value.create_graph_service_client.return_value = (
            mock_client
        )

        mock_client.subscriptions.get.return_value.value = []

        mock_result = MagicMock(id="new_sub123")
        mock_client.subscriptions.post.return_value = mock_result

        result = await subscribe_chat_messages(
            self.chat_id, self.notification_url, self.lifecycle_url
        )

        self.assertIn("subscription_id", result[1])
        self.assertEqual(result[1]["chat_id"], self.chat_id)
        mock_client.subscriptions.post.assert_awaited_once()
        mock_client.subscriptions.get.assert_awaited_once()
        mock_update_client_state.assert_called_once()
        mock_generate_client_state.assert_called_once()

    @patch("src.notification_management.microsoft_chat_watcher._generate_client_state")
    @patch("src.notification_management.microsoft_chat_watcher._update_client_state")
    @patch("src.notification_management.microsoft_chat_watcher.datetime")
    @patch("src.notification_management.microsoft_chat_watcher.MicrosoftClientFactory")
    async def test_existing_valid_subscription(
        self,
        mock_ms_factory,
        mock_datetime,
        mock_update_client_state,
        mock_generate_client_state,
    ):
        """Test when a valid existing subscription is found"""
        mock_datetime.now.return_value = self.current_time
        mock_client = AsyncMock()
        mock_ms_factory.return_value.create_graph_service_client.return_value = (
            mock_client
        )

        mock_client.subscriptions.get.return_value.value = [self.valid_subscription]

        result = await subscribe_chat_messages(
            self.chat_id, self.notification_url, self.lifecycle_url
        )

        self.assertEqual(result[1]["subscription_id"], self.valid_subscription.id)
        mock_client.subscriptions.get.assert_awaited_once()
        mock_client.subscriptions.post.assert_not_awaited()
        mock_update_client_state.assert_not_called()
        mock_generate_client_state.assert_not_called()

    @patch("src.notification_management.microsoft_chat_watcher._generate_client_state")
    @patch("src.notification_management.microsoft_chat_watcher._update_client_state")
    @patch("src.notification_management.microsoft_chat_watcher.datetime")
    @patch("src.notification_management.microsoft_chat_watcher.MicrosoftClientFactory")
    async def test_delete_existing_subscription(
        self,
        mock_ms_factory,
        mock_datetime,
        mock_update_client_state,
        mock_generate_client_state,
    ):
        """Test deleting an existing subscription with different change types and creating a new one"""
        mock_datetime.now.return_value = self.current_time

        mock_client = AsyncMock()
        mock_ms_factory.return_value.create_graph_service_client.return_value = (
            mock_client
        )

        different_change_sub = MagicMock(
            resource=MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE.format(
                chat_id=self.chat_id
            ),
            expiration_date_time=self.current_time + timedelta(hours=1),
            change_type="created",
            id="sub789",
        )
        mock_client.subscriptions.get.return_value.value = [different_change_sub]

        delete_mock = AsyncMock()
        mock_sub_api = MagicMock(delete=delete_mock)
        mock_client.subscriptions.by_subscription_id = MagicMock(
            return_value=mock_sub_api
        )

        created_subscription = MagicMock(id="new_sub123")
        mock_client.subscriptions.post.return_value = created_subscription

        result = await subscribe_chat_messages(
            self.chat_id, self.notification_url, self.lifecycle_url
        )

        self.assertEqual(
            result[0], f"Subscription created successfully for chat_id {self.chat_id}."
        )
        self.assertIn("subscription_id", result[1])
        mock_client.subscriptions.by_subscription_id.assert_called_once_with("sub789")
        delete_mock.assert_awaited_once()
        mock_client.subscriptions.post.assert_awaited_once()
        mock_update_client_state.assert_called_once()
        mock_generate_client_state.assert_called_once()

    @patch("src.notification_management.microsoft_chat_watcher.MicrosoftClientFactory")
    async def test_client_creation_failure(self, mock_ms_factory):
        """Test when client creation fails"""
        mock_ms_factory.return_value.create_graph_service_client.return_value = None

        with self.assertRaises(ValueError) as context:
            await subscribe_chat_messages(
                self.chat_id, self.notification_url, self.lifecycle_url
            )

    async def test_missing_required_parameters(self):
        with self.assertRaises(ValueError) as context:
            await subscribe_chat_messages("", self.notification_url, self.lifecycle_url)
        self.assertIn("chat_id", str(context.exception))

        with self.assertRaises(ValueError) as context:
            await subscribe_chat_messages(self.chat_id, "", self.lifecycle_url)
        self.assertIn("notification_url", str(context.exception))

        with self.assertRaises(ValueError) as context:
            await subscribe_chat_messages(self.chat_id, self.notification_url, "")
        self.assertIn("lifecycle_notification_url", str(context.exception))

    def test_generate_client_state_length_and_uniqueness(self):
        client_state_1 = _generate_client_state()
        client_state_2 = _generate_client_state()

        self.assertIsInstance(client_state_1, str)
        self.assertGreaterEqual(
            len(client_state_1.encode("utf-8")),
            MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_CLIENT_STATE_BYTE_LENGTH,
        )
        self.assertNotEqual(client_state_1, client_state_2)

    @patch("src.notification_management.microsoft_chat_watcher.RedisClientFactory")
    def test_update_client_state_successful(self, mock_redis_factory):
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_client

        _update_client_state(self.sub_id, self.client_state, self.legacy_id)

        mock_pipeline.set.assert_called_once_with(
            MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY.format(
                subscription_id=self.sub_id
            ),
            self.client_state,
        )
        mock_pipeline.delete.assert_called_once_with(
            MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY.format(
                subscription_id=self.legacy_id
            )
        )
        mock_pipeline.execute.assert_called_once()

    @patch("src.notification_management.microsoft_chat_watcher.RedisClientFactory")
    def test_update_client_state_success_without_legacy(self, mock_redis_factory):
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_client

        _update_client_state(self.sub_id, self.client_state, None)

        mock_pipeline.set.assert_called_once()
        mock_pipeline.delete.assert_not_called()
        mock_pipeline.execute.assert_called_once()

    def test_update_client_state_missing_params(self):
        with self.assertRaises(ValueError):
            _update_client_state("", "abc", None)
        with self.assertRaises(ValueError):
            _update_client_state("abc", "", None)

    @patch("src.notification_management.microsoft_chat_watcher.RedisClientFactory")
    def test_update_client_state_redis_client_none(self, mock_redis_factory):
        mock_redis_factory.return_value.create_redis_client.return_value = None

        with self.assertRaises(ValueError):
            _update_client_state(self.sub_id, self.client_state, None)

    @patch("src.notification_management.microsoft_chat_watcher.RedisClientFactory")
    def test_update_client_state_pipeline_execution_fails(self, mock_redis_factory):
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.execute.side_effect = RuntimeError("Redis error")
        mock_client.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_client

        with self.assertRaises(RuntimeError) as context:
            _update_client_state(self.sub_id, self.client_state, self.legacy_id)

        self.assertIn("Failed to update the client_state", str(context.exception))


if __name__ == "__main__":
    main()
