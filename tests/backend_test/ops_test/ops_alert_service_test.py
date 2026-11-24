import logging
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

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
        self.session = Mock()

    async def test_first_alert_is_raised_without_touching_the_database(self):
        """The alert reaches people through Cloud Monitoring, so nothing is
        recorded for Purrf to deliver."""
        state = _state()

        raised = await self.service.raise_alert(
            self.session, state, "history_expired", "x"
        )

        self.assertTrue(raised)
        self.assertEqual(self.session.method_calls, [])
        self.assertEqual(state.last_alert_kind, "history_expired")
        self.assertIsNotNone(state.last_alert_at)

    async def test_same_kind_within_six_hours_is_suppressed(self):
        state = _state("sync_failed", timedelta(hours=5))

        raised = await self.service.raise_alert(self.session, state, "sync_failed", "x")

        self.assertFalse(raised)

    async def test_same_kind_after_six_hours_alerts_again(self):
        state = _state("sync_failed", timedelta(hours=7))

        raised = await self.service.raise_alert(self.session, state, "sync_failed", "x")

        self.assertTrue(raised)

    async def test_a_different_kind_is_never_suppressed(self):
        state = _state("sync_failed", timedelta(minutes=1))

        raised = await self.service.raise_alert(
            self.session, state, "watch_renewal_failed", "x"
        )

        self.assertTrue(raised)

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


if __name__ == "__main__":
    unittest.main()
