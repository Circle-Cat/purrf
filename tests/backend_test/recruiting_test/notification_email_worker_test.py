import asyncio
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
from backend.recruiting.notification_email_worker import NotificationEmailWorker


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


class _AsyncContext:
    """Minimal async context manager yielding a fixed value."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc_info):
        return False


class TestNotificationEmailWorker(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = MagicMock()
        self.session.begin = MagicMock(return_value=_AsyncContext(None))
        self.database = MagicMock()
        self.database.session = MagicMock(return_value=_AsyncContext(self.session))

        self.repo = MagicMock()
        self.repo.claim_unemailed = AsyncMock(return_value=[])
        self.repo.mark_emailed = AsyncMock()

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

        self.worker = NotificationEmailWorker(
            database=self.database,
            notification_repository=self.repo,
            notification_service=self.notification_service,
            user_emails_repository=self.user_emails_repo,
            email_service=self.email_service,
            logger=self.logger,
            sweep_seconds=0.01,
        )

    def _row(self, notification_id=1, user_id=5):
        row = NotificationEntity(
            user_id=user_id,
            type=NotificationType.ASSIGNED_TO_EVALUATE,
            application_id=10,
        )
        row.notification_id = notification_id
        return row

    def _claims(self, *rows):
        self.repo.claim_unemailed = AsyncMock(return_value=list(rows))

    async def test_drain_once_returns_zero_and_sends_nothing_on_empty_outbox(self):
        processed = await self.worker.drain_once()

        self.assertEqual(processed, 0)
        self.email_service.send.assert_not_awaited()
        self.repo.mark_emailed.assert_not_awaited()

    async def test_drain_once_emails_every_claimed_recipient(self):
        self._claims(self._row(1, user_id=5), self._row(2, user_id=6))

        processed = await self.worker.drain_once()

        self.assertEqual(processed, 2)
        self.assertEqual(
            sorted(call.args[0] for call in self.email_service.send.await_args_list),
            ["five@circlecat.org", "six@circlecat.org"],
        )

    async def test_drain_once_stamps_every_claimed_row(self):
        self._claims(self._row(1, user_id=5), self._row(2, user_id=6))

        await self.worker.drain_once()

        session, ids, sent_at = self.repo.mark_emailed.await_args.args
        self.assertEqual(sorted(ids), [1, 2])
        self.assertIsNotNone(sent_at)

    async def test_drain_once_stamps_a_recipient_with_no_email(self):
        """An unstampable row would be re-claimed forever and wedge the queue."""
        self.user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            return_value={}
        )
        self._claims(self._row(1))

        await self.worker.drain_once()

        self.email_service.send.assert_not_awaited()
        self.logger.warning.assert_called_once()
        self.assertEqual(self.repo.mark_emailed.await_args.args[1], [1])

    async def test_drain_once_stamps_a_row_that_fails_to_render(self):
        self.notification_service.resolve = AsyncMock(
            side_effect=[RuntimeError("boom"), (_dto(), ApplicationStage.TECH)]
        )
        self._claims(self._row(1, user_id=5), self._row(2, user_id=6))

        await self.worker.drain_once()

        self.email_service.send.assert_awaited_once()
        self.logger.error.assert_called_once()
        self.assertEqual(sorted(self.repo.mark_emailed.await_args.args[1]), [1, 2])

    async def test_drain_once_survives_one_send_raising_and_still_stamps(self):
        self.email_service.send = AsyncMock(side_effect=[RuntimeError("boom"), True])
        self._claims(self._row(1, user_id=5), self._row(2, user_id=6))

        await self.worker.drain_once()  # must not raise

        self.assertEqual(self.email_service.send.await_count, 2)
        self.assertEqual(sorted(self.repo.mark_emailed.await_args.args[1]), [1, 2])

    async def test_drain_once_leaves_rows_unstamped_when_lookup_fails(self):
        """The failure is about the batch, not the rows -- retry them intact."""
        self.user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            side_effect=RuntimeError("db down")
        )
        self._claims(self._row(1))

        with self.assertRaises(RuntimeError):
            await self.worker.drain_once()

        self.repo.mark_emailed.assert_not_awaited()
        self.logger.error.assert_called_once()

    async def test_drain_once_claims_in_bounded_batches(self):
        await self.worker.drain_once()

        _, limit = self.repo.claim_unemailed.await_args.args
        self.assertEqual(limit, 50)

    async def test_wake_is_idempotent_before_the_loop_runs(self):
        self.worker.wake()
        self.worker.wake()

        self.assertTrue(self.worker._wakeup.is_set())

    async def test_start_sweeps_immediately_without_being_woken(self):
        """A pod inheriting a backlog must drain it on boot."""
        self._claims(self._row(1))

        self.worker.start()
        await asyncio.sleep(0.05)
        await self.worker.stop()

        self.email_service.send.assert_awaited()

    async def test_loop_keeps_running_after_a_failing_sweep(self):
        self.repo.claim_unemailed = AsyncMock(
            side_effect=[RuntimeError("boom"), [self._row(1)], []]
        )

        self.worker.start()
        await asyncio.sleep(0.08)
        await self.worker.stop()

        self.logger.error.assert_called()
        self.email_service.send.assert_awaited()

    async def test_stop_is_safe_when_never_started(self):
        await self.worker.stop()  # must not raise

    async def test_stop_is_idempotent(self):
        self.worker.start()
        await self.worker.stop()
        await self.worker.stop()  # must not raise


if __name__ == "__main__":
    unittest.main()
