"""Syncs Inbox threads and records what their new mail calls for.

Registered in the email context registry for the three *_INBOX contexts and
ACTIVITY. A full resync calls ``resync_all`` once per registered context, so
only one context gets the full handler; the rest get
``alias_without_resync()``, which syncs a thread the same way but leaves the
sweep to the full handler.
"""

import logging

from backend.common.communication_enums import ContextType

INBOX_CONTEXT_TYPES = [
    ContextType.MENTORSHIP_INBOX,
    ContextType.RECRUITING_INBOX,
    ContextType.INQUIRIES_INBOX,
    ContextType.ACTIVITY,
]


class InboxSyncHandler:
    def __init__(self, conversation_service, thread_repository, notifier, logger):
        """
        Args:
            conversation_service (EmailConversationService): Pulls a thread from Gmail.
            thread_repository (EmailThreadRepository): Lists and re-reads threads.
            notifier (InboxNotifier): Records events for newly synced mail.
            logger: Application logger.
        """
        self._conversation = conversation_service
        self._threads = thread_repository
        self._notifier = notifier
        self._logger = logger

    async def sync_tracked_thread(self, session, thread, messages=None):
        """Sync one changed Inbox thread and record its events. Does not commit.

        Args:
            session (AsyncSession): The active DB session.
            thread (EmailThreadEntity): The thread that changed.
            messages (list[dict] | None): The thread's messages, already read
                from Gmail when it was just routed; None reads them here.

        Returns:
            int: Messages newly persisted.

        Raises:
            RateLimitedError / RuntimeError: Propagated from Gmail.
        """
        new_messages = await self._conversation.sync_thread(
            session, thread, fetched=messages
        )
        await self._notifier.after_sync(session, thread, new_messages)
        return len(new_messages)

    async def resync_all(self, session):
        """Sync every Inbox thread, each in its own savepoint. Commits per thread.

        A failing thread is rolled back, logged and counted, and the sweep
        moves on, as in ``EmailSyncService._sweep``.

        Args:
            session (AsyncSession): The active DB session.

        Returns:
            dict: ``{"threads": <synced>, "failed": <failed>}``.
        """
        threads = await self._threads.list_by_context_types(
            session, INBOX_CONTEXT_TYPES
        )
        # Plain ids: a rollback below expires every loaded entity.
        thread_ids = [t.thread_id for t in threads]
        synced = 0
        failed = 0
        for thread_id in thread_ids:
            try:
                async with session.begin_nested():
                    thread = await self._threads.get(session, thread_id)
                    await self.sync_tracked_thread(session, thread)
                await session.commit()
                synced += 1
            except Exception:
                await session.rollback()
                self._logger.exception(
                    "[InboxSync] thread_id=%s resync failed", thread_id
                )
                failed += 1
        self._logger.log(
            logging.WARNING if failed else logging.INFO,
            "[InboxSync] resync finished: threads=%d failed=%d",
            synced,
            failed,
        )
        return {"threads": synced, "failed": failed}

    def alias_without_resync(self):
        """A handler for another context: same sync, no second sweep."""
        return _ResyncFreeAlias(self)


class _ResyncFreeAlias:
    def __init__(self, handler):
        self._handler = handler

    async def sync_tracked_thread(self, session, thread, messages=None):
        return await self._handler.sync_tracked_thread(
            session, thread, messages=messages
        )

    async def resync_all(self, session):
        del session
        return {"threads": 0, "failed": 0}
