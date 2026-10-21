import unittest
from unittest.mock import AsyncMock, MagicMock, Mock

from backend.communication.gmail_maintenance_service import GmailMaintenanceService


class _FakeDatabase:
    def __init__(self, session):
        self.session_object = session

    def session(self):
        return self

    async def __aenter__(self):
        return self.session_object

    async def __aexit__(self, *exc_info):
        return False


class GmailMaintenanceServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.background_session = AsyncMock()
        self.sync_service = AsyncMock()
        self.sync_service.renew_watch.return_value = {
            "expiration": "2026-10-07T00:00:00+00:00"
        }
        self.sync_service.catch_up.return_value = {
            "threads": 1,
            "newMessages": 2,
            "failed": 0,
        }
        self.logger = MagicMock()
        self.service = GmailMaintenanceService(
            logger=self.logger,
            gmail_sync_service=self.sync_service,
            database=_FakeDatabase(self.background_session),
        )

    async def test_maintain_renews_then_catches_up(self):
        order = Mock()
        order.attach_mock(self.sync_service.renew_watch, "renew_watch")
        order.attach_mock(self.sync_service.catch_up, "catch_up")

        result = await self.service.maintain(self.session)

        self.assertEqual([c[0] for c in order.mock_calls], ["renew_watch", "catch_up"])
        self.sync_service.renew_watch.assert_awaited_once_with(self.session)
        self.sync_service.catch_up.assert_awaited_once_with(self.session)
        self.assertEqual(
            result,
            {
                "watch": {"expiration": "2026-10-07T00:00:00+00:00"},
                "catchUp": {"threads": 1, "newMessages": 2, "failed": 0},
            },
        )

    async def test_failed_renewal_rolls_back_still_catches_up_then_propagates(self):
        self.sync_service.renew_watch.side_effect = RuntimeError("watch failed")

        with self.assertRaises(RuntimeError) as raised:
            await self.service.maintain(self.session)

        self.assertEqual(str(raised.exception), "watch failed")
        self.session.rollback.assert_awaited_once()
        self.sync_service.catch_up.assert_awaited_once_with(self.session)

    async def test_renewal_error_wins_over_a_catch_up_error(self):
        self.sync_service.renew_watch.side_effect = RuntimeError("watch failed")
        self.sync_service.catch_up.side_effect = ValueError("catch-up failed")

        with self.assertRaises(RuntimeError) as raised:
            await self.service.maintain(self.session)

        self.assertEqual(str(raised.exception), "watch failed")
        self.logger.exception.assert_called_once()

    async def test_catch_up_failure_propagates(self):
        self.sync_service.catch_up.side_effect = RuntimeError("catch-up failed")

        with self.assertRaises(RuntimeError):
            await self.service.maintain(self.session)

    async def test_manual_full_resync_runs_on_its_own_session_without_alerting(self):
        await self.service.run_manual_full_resync()

        self.sync_service.full_resync.assert_awaited_once_with(
            self.background_session, alert=False
        )

    async def test_failed_manual_full_resync_is_logged_not_raised(self):
        self.sync_service.full_resync.side_effect = RuntimeError("db down")

        await self.service.run_manual_full_resync()

        self.logger.exception.assert_called_once()


if __name__ == "__main__":
    unittest.main()
