import json
from unittest import IsolatedAsyncioTestCase, main
from src.common.constants import MicrosoftChatMessagesChangeType
from unittest.mock import patch, MagicMock, AsyncMock
from src.consumers.microsoft_chat_consumer import (
    process_data_async,
    pull_microsoft_message,
)

TEST_RESOURCE = "/chats/123/messages/456"
TEST_MESSAGE_ID = "abc"

TEST_VALID_PROJECT_ID = "my-project"
TEST_VALID_SUBSCRIPTION_ID = "my-sub"
TEST_INVALID_PROJECT_ID = ""
TEST_INVALID_SUBSCRIPTION_ID = ""


class TestMicrosoftChatConsumer(IsolatedAsyncioTestCase):
    def _make_mock_message(self, change_type, resource, message_id):
        message = MagicMock()
        message.data = json.dumps({
            "changeType": change_type,
            "resource": resource,
        }).encode("utf-8")
        message.ack = MagicMock()
        message.nack = MagicMock()
        message.message_id = message_id
        return message

    @patch(
        "src.consumers.microsoft_chat_consumer.sync_near_real_time_message_to_redis",
        new_callable=AsyncMock,
    )
    async def test_process_data_async_success(self, MagicMock_sync):
        message = self._make_mock_message(
            MicrosoftChatMessagesChangeType.CREATED.value,
            TEST_RESOURCE,
            TEST_MESSAGE_ID,
        )

        await process_data_async(message)

        MagicMock_sync.assert_awaited_once_with(
            MicrosoftChatMessagesChangeType.CREATED.value, TEST_RESOURCE
        )
        message.ack.assert_called_once()
        message.nack.assert_not_called()

    @patch(
        "src.consumers.microsoft_chat_consumer.sync_near_real_time_message_to_redis",
        new_callable=AsyncMock,
    )
    @patch("src.consumers.microsoft_chat_consumer.logger")
    async def test_process_data_async_exception(self, MagicMock_logger, MagicMock_sync):
        message = self._make_mock_message(
            MicrosoftChatMessagesChangeType.CREATED.value,
            TEST_RESOURCE,
            TEST_MESSAGE_ID,
        )

        MagicMock_sync.side_effect = Exception()

        await process_data_async(message)

        message.ack.assert_not_called()
        message.nack.assert_called_once()
        MagicMock_logger.error.assert_called_once()

    @patch("src.consumers.microsoft_chat_consumer.PubSubPuller")
    def test_pull_microsoft_message_success(self, mock_puller_class):
        mock_instance = MagicMock()
        mock_puller_class.return_value = mock_instance

        pull_microsoft_message(TEST_VALID_PROJECT_ID, TEST_VALID_SUBSCRIPTION_ID)
        mock_puller_class.assert_called_once_with(
            TEST_VALID_PROJECT_ID, TEST_VALID_SUBSCRIPTION_ID
        )
        mock_instance.start_pulling_messages.assert_called_once()

    def test_pull_microsoft_message_invalid_project(self):
        with self.assertRaises(ValueError):
            pull_microsoft_message(TEST_INVALID_PROJECT_ID, TEST_VALID_PROJECT_ID)

    def test_pull_microsoft_message_invalid_subscription(self):
        with self.assertRaises(ValueError):
            pull_microsoft_message(TEST_VALID_PROJECT_ID, TEST_INVALID_SUBSCRIPTION_ID)


if __name__ == "__main__":
    main()
