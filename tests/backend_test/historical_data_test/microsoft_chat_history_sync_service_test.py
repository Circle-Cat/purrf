import unittest
from unittest.mock import AsyncMock, Mock, call, patch

from backend.historical_data.microsoft_chat_history_sync_service import (
    MicrosoftChatHistorySyncService,
)


async def async_generator(items):
    for item in items:
        yield item


class TestMicrosoftChatHistorySyncService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = Mock()
        self.microsoft_service = AsyncMock()
        self.microsoft_chat_message_util = Mock()
        self.service = MicrosoftChatHistorySyncService(
            self.logger, self.microsoft_service, self.microsoft_chat_message_util
        )
        self.chat_id = "test_chat_id"

    async def test_get_microsoft_chat_messages_by_chat_id_single_page(self):
        mock_page = Mock()
        mock_page.value = [{"id": "msg1"}, {"id": "msg2"}]
        mock_page.odata_next_link = None
        self.microsoft_service.fetch_initial_chat_messages_page.return_value = mock_page

        messages_gen = self.service.get_microsoft_chat_messages_by_chat_id(self.chat_id)
        pages = [page async for page in messages_gen]

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0], mock_page.value)
        self.microsoft_service.fetch_initial_chat_messages_page.assert_awaited_once_with(
            chat_id=self.chat_id
        )
        self.microsoft_service.fetch_chat_messages_by_url.assert_not_awaited()

    async def test_get_microsoft_chat_messages_by_chat_id_multiple_pages(self):
        mock_page1 = Mock()
        mock_page1.value = [{"id": "msg1"}, {"id": "msg2"}]
        mock_page1.odata_next_link = "next_link_url"

        mock_page2 = Mock()
        mock_page2.value = [{"id": "msg3"}, {"id": "msg4"}]
        mock_page2.odata_next_link = None

        self.microsoft_service.fetch_initial_chat_messages_page.return_value = (
            mock_page1
        )
        self.microsoft_service.fetch_chat_messages_by_url.return_value = mock_page2

        messages_gen = self.service.get_microsoft_chat_messages_by_chat_id(self.chat_id)
        pages = [page async for page in messages_gen]

        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0], mock_page1.value)
        self.assertEqual(pages[1], mock_page2.value)
        self.microsoft_service.fetch_initial_chat_messages_page.assert_awaited_once_with(
            chat_id=self.chat_id
        )
        self.microsoft_service.fetch_chat_messages_by_url.assert_awaited_once_with(
            chat_id=self.chat_id, url="next_link_url"
        )

    async def test_get_microsoft_chat_messages_by_chat_id_no_messages(self):
        mock_page = Mock()
        mock_page.value = []
        mock_page.odata_next_link = None
        self.microsoft_service.fetch_initial_chat_messages_page.return_value = mock_page

        messages_gen = self.service.get_microsoft_chat_messages_by_chat_id(self.chat_id)
        pages = [page async for page in messages_gen]

        self.assertEqual(len(pages), 0)
        self.microsoft_service.fetch_initial_chat_messages_page.assert_awaited_once_with(
            chat_id=self.chat_id
        )

    async def test_get_microsoft_chat_messages_by_chat_id_empty_page_in_middle(self):
        mock_page1 = Mock(value=[{"id": "msg1"}], odata_next_link="next_link_1")
        mock_page2 = Mock(value=[], odata_next_link="next_link_2")
        mock_page3 = Mock(value=[{"id": "msg2"}], odata_next_link=None)

        self.microsoft_service.fetch_initial_chat_messages_page.return_value = (
            mock_page1
        )
        self.microsoft_service.fetch_chat_messages_by_url.side_effect = [
            mock_page2,
            mock_page3,
        ]

        messages_gen = self.service.get_microsoft_chat_messages_by_chat_id(self.chat_id)
        pages = [page async for page in messages_gen]

        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0], mock_page1.value)
        self.assertEqual(pages[1], mock_page3.value)
        self.microsoft_service.fetch_chat_messages_by_url.assert_has_awaits([
            call(chat_id=self.chat_id, url="next_link_1"),
            call(chat_id=self.chat_id, url="next_link_2"),
        ])

    @patch(
        "backend.historical_data.microsoft_chat_history_sync_service.MicrosoftChatHistorySyncService.get_microsoft_chat_messages_by_chat_id"
    )
    async def test_sync_microsoft_chat_messages_by_chat_id_full_buffer_and_remainder(
        self, mock_get_messages
    ):
        all_ldaps = {"user1": "ldap1"}
        self.microsoft_service.list_all_id_ldap_mapping.return_value = all_ldaps

        pages = [[{"id": f"msg_p{i}"}] for i in range(11)]
        mock_get_messages.return_value = async_generator(pages)

        self.microsoft_chat_message_util.sync_history_chat_messages_to_redis.side_effect = [
            (10, 1),
            (1, 0),
        ]

        result = await self.service.sync_microsoft_chat_messages_by_chat_id(
            self.chat_id
        )
        self.assertIsNone(result)

        mock_get_messages.assert_called_once_with(self.chat_id)
        self.microsoft_service.list_all_id_ldap_mapping.assert_awaited_once()

        self.assertEqual(
            self.microsoft_chat_message_util.sync_history_chat_messages_to_redis.call_count,
            2,
        )

        batched_messages = [msg for page in pages[:10] for msg in page]
        remainder_messages = pages[10]
        self.microsoft_chat_message_util.sync_history_chat_messages_to_redis.assert_has_calls([
            call(batched_messages, all_ldaps),
            call(remainder_messages, all_ldaps),
        ])

    @patch(
        "backend.historical_data.microsoft_chat_history_sync_service.MicrosoftChatHistorySyncService.get_microsoft_chat_messages_by_chat_id"
    )
    async def test_sync_microsoft_chat_messages_by_chat_id_less_than_buffer(
        self, mock_get_messages
    ):
        all_ldaps = {"user1": "ldap1"}
        self.microsoft_service.list_all_id_ldap_mapping.return_value = all_ldaps

        pages = [[{"id": "msg1"}], [{"id": "msg2"}]]
        mock_get_messages.return_value = async_generator(pages)
        self.microsoft_chat_message_util.sync_history_chat_messages_to_redis.return_value = (
            10,
            1,
        )

        result = await self.service.sync_microsoft_chat_messages_by_chat_id(
            self.chat_id
        )
        self.assertIsNone(result)

        self.microsoft_chat_message_util.sync_history_chat_messages_to_redis.assert_called_once_with(
            pages[0] + pages[1], all_ldaps
        )

    @patch(
        "backend.historical_data.microsoft_chat_history_sync_service.MicrosoftChatHistorySyncService.get_microsoft_chat_messages_by_chat_id"
    )
    async def test_sync_microsoft_chat_messages_by_chat_id_no_messages(
        self, mock_get_messages
    ):
        self.microsoft_service.list_all_id_ldap_mapping.return_value = {}
        mock_get_messages.return_value = async_generator([])

        result = await self.service.sync_microsoft_chat_messages_by_chat_id(
            self.chat_id
        )
        self.assertIsNone(result)

        self.microsoft_chat_message_util.sync_history_chat_messages_to_redis.assert_not_called()
