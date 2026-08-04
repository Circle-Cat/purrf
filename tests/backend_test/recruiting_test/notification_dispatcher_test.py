import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.common.recruiting_enums import NotificationType
from backend.entity.notification_entity import NotificationEntity
from backend.recruiting.notification_dispatcher import NotificationDispatcher


class TestNotificationDispatcher(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repo = MagicMock()
        self.repo.create = AsyncMock(side_effect=lambda s, e: e)
        self.email_worker = MagicMock()
        self.session = MagicMock()
        self.dispatcher = NotificationDispatcher(
            notification_repository=self.repo,
            email_worker=self.email_worker,
        )

    def _entity(self, user_id=5):
        return NotificationEntity(
            user_id=user_id,
            type=NotificationType.ASSIGNED_TO_EVALUATE,
            application_id=10,
        )

    async def test_record_writes_the_row_in_the_callers_session(self):
        entity = self._entity()

        returned = await self.dispatcher.record(self.session, entity)

        self.repo.create.assert_awaited_once_with(self.session, entity)
        self.assertIs(returned, entity)

    async def test_record_does_not_wake_the_worker(self):
        """The row is not committed yet; waking now could email a rollback."""
        await self.dispatcher.record(self.session, self._entity())

        self.email_worker.wake.assert_not_called()

    async def test_flush_wakes_the_worker(self):
        await self.dispatcher.flush()

        self.email_worker.wake.assert_called_once_with()

    async def test_flush_touches_neither_database_nor_email(self):
        """It runs on the request path, so it must stay free of round trips."""
        await self.dispatcher.flush()

        self.repo.create.assert_not_awaited()

    async def test_flush_is_safe_when_nothing_was_recorded(self):
        await self.dispatcher.flush()  # must not raise

        self.email_worker.wake.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
