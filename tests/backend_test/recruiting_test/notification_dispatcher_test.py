import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
    NotificationType,
)
from backend.dto.notification_dto import NotificationDto
from backend.entity.notification_entity import NotificationEntity
from backend.recruiting.notification_dispatcher import NotificationDispatcher


def _dto(**overrides):
    defaults = dict(
        id=1,
        type=NotificationType.ASSIGNED_TO_EVALUATE,
        application_id=10,
        job_id=3,
        round=1,
        job_title="Backend Engineer",
        job_kind=JobKind.EMPLOYMENT,
        applicant_name="Ada Lovelace",
        actor_name="Grace Hopper",
        created_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return NotificationDto(**defaults)


class TestNotificationDispatcher(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repo = MagicMock()
        self.repo.create = AsyncMock(side_effect=lambda s, e: e)
        self.notification_service = MagicMock()
        self.notification_service.resolve = AsyncMock(
            return_value=(_dto(), ApplicationStage.TECH)
        )
        self.user_emails_repo = MagicMock()
        self.user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            return_value={5: "five@circlecat.org", 6: "six@circlecat.org"}
        )
        self.email_service = MagicMock()
        self.email_service.send = AsyncMock(return_value=True)
        self.logger = MagicMock()
        self.session = MagicMock()
        self.session.info = {}
        self.dispatcher = NotificationDispatcher(
            notification_repository=self.repo,
            notification_service=self.notification_service,
            user_emails_repository=self.user_emails_repo,
            email_service=self.email_service,
            logger=self.logger,
        )

    def _entity(self, user_id=5):
        return NotificationEntity(
            user_id=user_id,
            type=NotificationType.ASSIGNED_TO_EVALUATE,
            application_id=10,
        )

    async def test_record_writes_the_row_and_sends_nothing_yet(self):
        await self.dispatcher.record(self.session, self._entity())

        self.repo.create.assert_awaited_once()
        self.email_service.send.assert_not_awaited()

    async def test_flush_emails_every_recorded_recipient(self):
        await self.dispatcher.record(self.session, self._entity(user_id=5))
        await self.dispatcher.record(self.session, self._entity(user_id=6))

        await self.dispatcher.flush(self.session)

        self.assertEqual(
            sorted(call.args[0] for call in self.email_service.send.await_args_list),
            ["five@circlecat.org", "six@circlecat.org"],
        )

    async def test_flush_is_a_no_op_without_anything_recorded(self):
        await self.dispatcher.flush(self.session)

        self.email_service.send.assert_not_awaited()
        self.user_emails_repo.get_contact_emails_by_user_ids.assert_not_awaited()

    async def test_flush_clears_the_buffer_so_a_second_flush_resends_nothing(self):
        await self.dispatcher.record(self.session, self._entity())
        await self.dispatcher.flush(self.session)
        self.email_service.send.reset_mock()

        await self.dispatcher.flush(self.session)

        self.email_service.send.assert_not_awaited()

    async def test_flush_skips_a_recipient_with_no_email_and_warns(self):
        self.user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            return_value={}
        )
        await self.dispatcher.record(self.session, self._entity())

        await self.dispatcher.flush(self.session)

        self.email_service.send.assert_not_awaited()
        self.logger.warning.assert_called_once()

    async def test_flush_keeps_going_when_one_notification_fails_to_render(self):
        self.notification_service.resolve = AsyncMock(
            side_effect=[RuntimeError("boom"), (_dto(), ApplicationStage.TECH)]
        )
        await self.dispatcher.record(self.session, self._entity(user_id=5))
        await self.dispatcher.record(self.session, self._entity(user_id=6))

        await self.dispatcher.flush(self.session)

        self.email_service.send.assert_awaited_once()
        self.logger.error.assert_called_once()

    async def test_flush_never_raises_when_sending_fails(self):
        self.email_service.send = AsyncMock(return_value=False)
        await self.dispatcher.record(self.session, self._entity())

        await self.dispatcher.flush(self.session)  # must not raise

    async def test_flush_survives_one_send_raising_and_still_sends_the_rest(self):
        self.email_service.send = AsyncMock(side_effect=[RuntimeError("boom"), True])
        await self.dispatcher.record(self.session, self._entity(user_id=5))
        await self.dispatcher.record(self.session, self._entity(user_id=6))

        await self.dispatcher.flush(self.session)  # must not raise

        self.assertEqual(self.email_service.send.await_count, 2)

    async def test_flush_never_raises_when_recipient_lookup_fails(self):
        self.user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            side_effect=RuntimeError("db down")
        )
        await self.dispatcher.record(self.session, self._entity())

        await self.dispatcher.flush(self.session)  # must not raise

        self.email_service.send.assert_not_awaited()
        self.logger.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
