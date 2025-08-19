import json
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock
from backend.consumers.microsoft_message_processor_service import (
    MicrosoftMessageProcessorService,
)

TEST_RESOURCE = "/chats/123/messages/456"
TEST_MESSAGE_ID = "abc"
TEST_VALID_PROJECT_ID = "my-project"
TEST_VALID_SUBSCRIPTION_ID = "my-sub"
TEST_INVALID_PROJECT_ID = ""
TEST_INVALID_SUBSCRIPTION_ID = ""
TEST_CHANGE_TYPE = "created"


class TestMicrosoftMessageProcessorService(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.logger = MagicMock()
        self.mock_sync_util = AsyncMock()
        self.mock_puller_factory = MagicMock()
        self.service = MicrosoftMessageProcessorService(
            logger=self.logger,
            pubsub_puller_factory=self.mock_puller_factory,
            microsoft_chat_message_util=self.mock_sync_util,
        )

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

    async def test_process_data_async_success(self):
        message = self._make_mock_message(
            TEST_CHANGE_TYPE,
            TEST_RESOURCE,
            TEST_MESSAGE_ID,
        )
        await self.service.process_data_async(message)
        self.mock_sync_util.sync_near_real_time_message_to_redis.assert_awaited_once_with(
            TEST_CHANGE_TYPE, TEST_RESOURCE
        )
        message.ack.assert_called_once()
        message.nack.assert_not_called()

    async def test_process_data_async_exception(self):
        message = self._make_mock_message(
            TEST_CHANGE_TYPE,
            TEST_RESOURCE,
            TEST_MESSAGE_ID,
        )
        self.mock_sync_util.sync_near_real_time_message_to_redis.side_effect = (
            Exception("Test error")
        )
        await self.service.process_data_async(message)
        message.ack.assert_not_called()
        message.nack.assert_called_once()
        self.logger.error.assert_called_once_with(
            f"Error processing message {message.message_id}: Test error", exc_info=True
        )

    def test_pull_microsoft_message_success(self):
        mock_puller = MagicMock()
        self.mock_puller_factory.get_puller_instance.return_value = mock_puller
        self.service.pull_microsoft_message(
            TEST_VALID_PROJECT_ID, TEST_VALID_SUBSCRIPTION_ID
        )
        self.mock_puller_factory.get_puller_instance.assert_called_once_with(
            TEST_VALID_PROJECT_ID, TEST_VALID_SUBSCRIPTION_ID
        )
        mock_puller.start_pulling_messages.assert_called_once_with(
            self.service.process_data_async
        )

    def test_pull_microsoft_message_invalid_project(self):
        with self.assertRaises(ValueError):
            self.service.pull_microsoft_message(
                TEST_INVALID_PROJECT_ID, TEST_VALID_SUBSCRIPTION_ID
            )

    def test_pull_microsoft_message_invalid_subscription(self):
        with self.assertRaises(ValueError):
            self.service.pull_microsoft_message(
                TEST_VALID_PROJECT_ID, TEST_INVALID_SUBSCRIPTION_ID
            )


if __name__ == "__main__":
    main()
