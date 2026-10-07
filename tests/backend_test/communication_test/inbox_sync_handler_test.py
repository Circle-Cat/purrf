import unittest
from unittest.mock import AsyncMock, MagicMock, Mock

from backend.common.communication_enums import ContextType
from backend.communication.inbox_sync_handler import InboxSyncHandler


def _session():
    session = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    savepoint = MagicMock()
    savepoint.__aenter__ = AsyncMock()
    savepoint.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = Mock(return_value=savepoint)
    return session


class InboxSyncHandlerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conversation = AsyncMock()
        self.threads = AsyncMock()
        self.notifier = AsyncMock()
        self.logger = Mock()
        self.handler = InboxSyncHandler(
            conversation_service=self.conversation,
            thread_repository=self.threads,
            notifier=self.notifier,
            logger=self.logger,
        )
        self.session = _session()

    async def test_sync_hands_the_new_messages_to_the_notifier(self):
        thread = Mock(thread_id=5)
        new = [Mock(), Mock()]
        self.conversation.sync_thread.return_value = new

        count = await self.handler.sync_tracked_thread(self.session, thread)

        self.assertEqual(count, 2)
        self.conversation.sync_thread.assert_awaited_once_with(self.session, thread)
        self.notifier.after_sync.assert_awaited_once_with(self.session, thread, new)
        self.session.commit.assert_not_awaited()

    async def test_resync_syncs_every_inbox_thread_and_commits_each(self):
        a, b = Mock(thread_id=1), Mock(thread_id=2)
        self.threads.list_by_context_types.return_value = [a, b]
        self.threads.get.side_effect = lambda session, tid: {1: a, 2: b}[tid]
        self.conversation.sync_thread.return_value = []
        events = []
        self.conversation.sync_thread.side_effect = (
            lambda s, t: events.append(("sync", t.thread_id)) or []
        )
        self.session.commit.side_effect = lambda: events.append(("commit",))

        result = await self.handler.resync_all(self.session)

        self.assertEqual(result, {"threads": 2, "failed": 0})
        self.threads.list_by_context_types.assert_awaited_once_with(
            self.session,
            [
                ContextType.MENTORSHIP_INBOX,
                ContextType.RECRUITING_INBOX,
                ContextType.INQUIRIES_INBOX,
                ContextType.ACTIVITY,
            ],
        )
        self.assertEqual(events, [("sync", 1), ("commit",), ("sync", 2), ("commit",)])
        self.assertEqual(self.session.begin_nested.call_count, 2)

    async def test_one_failing_thread_does_not_stop_the_resync(self):
        a, b = Mock(thread_id=1), Mock(thread_id=2)
        self.threads.list_by_context_types.return_value = [a, b]
        self.threads.get.side_effect = lambda session, tid: {1: a, 2: b}[tid]

        async def sync(session, thread):
            if thread.thread_id == 1:
                raise RuntimeError("429")
            return [Mock()]

        self.conversation.sync_thread.side_effect = sync

        result = await self.handler.resync_all(self.session)

        self.assertEqual(result, {"threads": 1, "failed": 1})
        self.session.rollback.assert_awaited_once()
        self.assertEqual(self.session.commit.await_count, 1)
        self.notifier.after_sync.assert_awaited_once()
        self.logger.exception.assert_called_once()

    async def test_the_alias_syncs_like_the_handler_but_never_resyncs(self):
        alias = self.handler.alias_without_resync()
        thread = Mock(thread_id=5)
        self.conversation.sync_thread.return_value = [Mock()]

        self.assertEqual(await alias.sync_tracked_thread(self.session, thread), 1)
        self.notifier.after_sync.assert_awaited_once()

        self.assertEqual(
            await alias.resync_all(self.session), {"threads": 0, "failed": 0}
        )
        self.threads.list_by_context_types.assert_not_awaited()
        self.assertEqual(self.session.commit.await_args_list, [])


if __name__ == "__main__":
    unittest.main()
