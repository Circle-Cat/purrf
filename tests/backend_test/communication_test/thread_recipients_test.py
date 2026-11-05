import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.communication.thread_recipients import thread_senders, thread_senders_else
from backend.repository.email_message_repository import EmailMessageRepository


class ThreadRecipientsTest(unittest.IsolatedAsyncioTestCase):
    def _senders(self, ids):
        return patch.object(
            EmailMessageRepository,
            "list_sender_ids_by_thread",
            new_callable=AsyncMock,
            return_value=set(ids),
        )

    async def test_senders_are_read_for_the_thread(self):
        session = Mock()
        with self._senders({4, 5}) as lookup:
            self.assertEqual(await thread_senders(session, 31), {4, 5})
        lookup.assert_awaited_once_with(session, 31)

    async def test_senders_win_over_the_fallback(self):
        fallback = AsyncMock(return_value=[8])
        with self._senders({4}):
            self.assertEqual(await thread_senders_else(Mock(), 31, fallback), {4})
        fallback.assert_not_awaited()

    async def test_nobody_sent_through_purrf_asks_the_fallback(self):
        fallback = AsyncMock(return_value=[8, 9, 8])
        with self._senders(set()):
            self.assertEqual(await thread_senders_else(Mock(), 31, fallback), {8, 9})
        fallback.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
