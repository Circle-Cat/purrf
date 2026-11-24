import logging
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

from backend.ops.ops_alert_service import OpsAlertService


def _state(kind=None, age=None):
    return Mock(
        id=3,
        email_address="purrf@example.com",
        last_alert_kind=kind,
        last_alert_at=None if age is None else datetime.now(timezone.utc) - age,
    )


class OpsAlertServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = OpsAlertService(logging.getLogger("test"))
        patcher = patch(
            "backend.ops.ops_alert_service.record_event", new_callable=AsyncMock
        )
        self.record_event = patcher.start()
        self.addCleanup(patcher.stop)
        self.session = Mock()

    async def test_first_alert_records_an_event(self):
        state = _state()

        raised = await self.service.raise_alert(
            self.session, state, "history_expired", "x"
        )

        self.assertTrue(raised)
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="gmail_sync_state",
            subject_id=3,
            actor_id=None,
            event_type="ops.gmail_sync_alert",
            details={
                "kind": "history_expired",
                "detail": "x",
                "mailbox": "purrf@example.com",
            },
        )
        self.assertEqual(state.last_alert_kind, "history_expired")
        self.assertIsNotNone(state.last_alert_at)

    async def test_same_kind_within_six_hours_is_suppressed(self):
        state = _state("sync_failed", timedelta(hours=5))

        raised = await self.service.raise_alert(self.session, state, "sync_failed", "x")

        self.assertFalse(raised)
        self.record_event.assert_not_awaited()

    async def test_same_kind_after_six_hours_alerts_again(self):
        state = _state("sync_failed", timedelta(hours=7))

        raised = await self.service.raise_alert(self.session, state, "sync_failed", "x")

        self.assertTrue(raised)
        self.record_event.assert_awaited_once()

    async def test_a_different_kind_is_never_suppressed(self):
        state = _state("sync_failed", timedelta(minutes=1))

        raised = await self.service.raise_alert(
            self.session, state, "watch_renewal_failed", "x"
        )

        self.assertTrue(raised)
        self.record_event.assert_awaited_once()

    async def test_an_alert_is_logged_for_cloud_monitoring(self):
        """Cloud Monitoring alerts on this structured line, so it must not
        depend on Purrf being able to deliver anything."""
        logger = Mock()
        service = OpsAlertService(logger)

        await service.raise_alert(
            self.session, _state(), "watch_renewal_failed", "token refresh rejected"
        )

        logger.warning.assert_called_once()
        args, kwargs = logger.warning.call_args
        self.assertIn("token refresh rejected", args[0] % args[1:])
        self.assertEqual(
            kwargs["extra"],
            {
                "monitor_event": "gmail_sync.alert",
                "kind": "watch_renewal_failed",
                "mailbox": "purrf@example.com",
            },
        )

    async def test_a_suppressed_alert_is_not_logged(self):
        logger = Mock()
        service = OpsAlertService(logger)

        await service.raise_alert(
            self.session, _state("sync_failed", timedelta(hours=1)), "sync_failed", "x"
        )

        logger.warning.assert_not_called()

    async def test_detail_is_truncated(self):
        await self.service.raise_alert(
            self.session, _state(), "sync_failed", "a" * 2000
        )

        details = self.record_event.await_args.kwargs["details"]
        self.assertEqual(len(details["detail"]), 500)


if __name__ == "__main__":
    unittest.main()
