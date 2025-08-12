from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, patch, MagicMock
from types import SimpleNamespace
from backend.historical_data.microsoft_chat_history_fetcher import (
    list_all_id_ldap_mapping,
    get_microsoft_chat_messages_by_chat_id,
    sync_microsoft_chat_messages_by_chat_id,
    sync_history_chat_messages_to_redis,
)


class TestMicrosoftChatHistoryFetcher(IsolatedAsyncioTestCase):
    TEST_USER_ID_1 = "user1"
    TEST_USER_ID_2 = "user2"
    TEST_USER_EMAIL_1 = "alice@example.com"
    TEST_USER_EMAIL_2 = "bob@example.com"
    TEST_USER_LDAP_1 = "alice"
    TEST_USER_LDAP_2 = "bob"
    TEST_USER_1 = SimpleNamespace(id=TEST_USER_ID_1, mail=TEST_USER_EMAIL_1)
    TEST_USER_2 = SimpleNamespace(id=TEST_USER_ID_2, mail=TEST_USER_EMAIL_2)
    TEST_ALL_USER_INFO = [TEST_USER_1, TEST_USER_2]

    TEST_CHAT_MESSAGES_PAGE_VALUE_1 = ["msg1", "msg2"]
    TEST_CHAT_MESSAGES_PAGE_VALUE_2 = ["msg3"]

    TEST_CHAT_MESSAGES_PAGE_1 = SimpleNamespace(
        value=TEST_CHAT_MESSAGES_PAGE_VALUE_1, odata_next_link="next-link"
    )
    TEST_CHAT_MESSAGES_PAGE_2 = SimpleNamespace(
        value=TEST_CHAT_MESSAGES_PAGE_VALUE_2, odata_next_link=None
    )

    TEST_CHAT_ID = "chat123"

    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.get_all_microsoft_members",
        new_callable=AsyncMock,
    )
    async def test_list_all_id_ldap_mapping(self, mock_get_members):
        mock_get_members.return_value = self.TEST_ALL_USER_INFO

        result = await list_all_id_ldap_mapping()
        self.assertEqual(
            result,
            {
                self.TEST_USER_ID_1: self.TEST_USER_LDAP_1,
                self.TEST_USER_ID_2: self.TEST_USER_LDAP_2,
            },
        )

    @patch("backend.historical_data.microsoft_chat_history_fetcher.MicrosoftClientFactory")
    async def test_get_microsoft_chat_messages_by_chat_id(self, mock_graph_factory):
        mock_get = AsyncMock(return_value=self.TEST_CHAT_MESSAGES_PAGE_1)
        mock_get_with_url = AsyncMock(return_value=self.TEST_CHAT_MESSAGES_PAGE_2)

        mock_with_url = MagicMock(return_value=mock_get_with_url)

        mock_messages = MagicMock()
        mock_messages.get = mock_get
        mock_messages.with_url = MagicMock(
            return_value=MagicMock(get=mock_get_with_url)
        )

        mock_chat = MagicMock(messages=mock_messages)
        mock_chats = MagicMock(by_chat_id=MagicMock(return_value=mock_chat))
        mock_graph_client = MagicMock(chats=mock_chats)
        mock_graph_factory.return_value.create_graph_service_client.return_value = (
            mock_graph_client
        )

        result = []
        async for page in get_microsoft_chat_messages_by_chat_id(self.TEST_CHAT_ID):
            result.extend(page)

        self.assertEqual(
            result,
            self.TEST_CHAT_MESSAGES_PAGE_VALUE_1 + self.TEST_CHAT_MESSAGES_PAGE_VALUE_2,
        )

    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.sync_history_chat_messages_to_redis"
    )
    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.get_microsoft_chat_messages_by_chat_id"
    )
    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.list_all_id_ldap_mapping",
        new_callable=AsyncMock,
    )
    async def test_no_messages(
        self, mock_list_ldap, mock_get_messages, mock_sync_to_redis
    ):
        async def mock_async_generator_empty():
            yield []
            yield []

        mock_get_messages.return_value = mock_async_generator_empty()

        result = await sync_microsoft_chat_messages_by_chat_id(self.TEST_CHAT_ID)

        mock_list_ldap.assert_called_once()
        mock_sync_to_redis.assert_not_called()

    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.sync_history_chat_messages_to_redis"
    )
    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.get_microsoft_chat_messages_by_chat_id"
    )
    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.list_all_id_ldap_mapping",
        new_callable=AsyncMock,
    )
    async def test_single_page_messages_no_buffer_flush(
        self, mock_list_ldap, mock_get_messages, mock_sync_to_redis
    ):
        async def mock_async_generator():
            yield self.TEST_CHAT_MESSAGES_PAGE_VALUE_1

        mock_get_messages.return_value = mock_async_generator()
        mock_list_ldap.return_value = {self.TEST_USER_ID_1: self.TEST_USER_LDAP_1}
        mock_sync_to_redis.return_value = (2, 0)

        result = await sync_microsoft_chat_messages_by_chat_id(self.TEST_CHAT_ID)

        mock_list_ldap.assert_called_once()
        mock_sync_to_redis.assert_called_once()

    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.sync_history_chat_messages_to_redis"
    )
    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.get_microsoft_chat_messages_by_chat_id"
    )
    @patch(
        "backend.historical_data.microsoft_chat_history_fetcher.list_all_id_ldap_mapping",
        new_callable=AsyncMock,
    )
    async def test_multiple_pages_with_buffer_flush(
        self, mock_list_ldap, mock_get_messages, mock_sync_to_redis
    ):
        async def mock_async_generator_multiple_pages():
            for _ in range(11):
                yield self.TEST_CHAT_MESSAGES_PAGE_VALUE_2

        mock_get_messages.return_value = mock_async_generator_multiple_pages()
        mock_list_ldap.return_value = {self.TEST_USER_ID_1: self.TEST_USER_LDAP_1}

        mock_sync_to_redis.side_effect = [(3, 0), (2, 0)]

        result = await sync_microsoft_chat_messages_by_chat_id(self.TEST_CHAT_ID)

        self.assertEqual(result, {"total_processed": 5, "total_skipped": 0})
        self.assertEqual(mock_sync_to_redis.call_count, 2)
        mock_list_ldap.assert_called_once()


if __name__ == "__main__":
    main()
