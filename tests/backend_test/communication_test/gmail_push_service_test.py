import base64
import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.communication.gmail_push_service import GmailPushService
from backend.communication.gmail_sync_service import PushOutcome


class _FakeDatabase:
    """Stands in for Database.session() -- an async context manager yielding a session."""

    def __init__(self, session):
        self.session_object = session

    def session(self):
        return self

    async def __aenter__(self):
        return self.session_object

    async def __aexit__(self, *exc_info):
        return False


_BEARER = "Bearer push-token"


def _envelope(payload):
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": data, "messageId": "1"}, "subscription": "s"}


class GmailPushServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sync_service = AsyncMock()
        self.sync_service.handle_push.return_value = PushOutcome.ACK
        self.session = AsyncMock()
        self.background_session = AsyncMock()
        self.auth_service = MagicMock()
        self.auth_service.verify_google_token.return_value = {"sub": "111-pusher"}
        self.logger = MagicMock()
        self.service = self._service(frozenset({"111-pusher"}))

    def _service(self, pusher_subs):
        return GmailPushService(
            logger=self.logger,
            gmail_sync_service=self.sync_service,
            auth_service=self.auth_service,
            pusher_subs=pusher_subs,
            database=_FakeDatabase(self.background_session),
        )

    async def _receive(self, envelope, authorization=_BEARER):
        return await self.service.receive(self.session, authorization, envelope)

    async def test_missing_bearer_is_refused(self):
        outcome = await self._receive(_envelope({}), authorization="")

        self.assertEqual(outcome, PushOutcome.REFUSED)
        self.auth_service.verify_google_token.assert_not_called()
        self.sync_service.handle_push.assert_not_awaited()

    async def test_unverifiable_token_is_refused(self):
        self.auth_service.verify_google_token.side_effect = ValueError("expired")

        outcome = await self._receive(_envelope({}))

        self.assertEqual(outcome, PushOutcome.REFUSED)
        self.sync_service.handle_push.assert_not_awaited()

    async def test_unknown_sub_is_refused(self):
        self.auth_service.verify_google_token.return_value = {"sub": "other"}

        outcome = await self._receive(_envelope({}))

        self.assertEqual(outcome, PushOutcome.REFUSED)
        self.sync_service.handle_push.assert_not_awaited()

    async def test_empty_allowlist_refuses_everyone(self):
        self.service = self._service(frozenset())

        outcome = await self._receive(_envelope({}))

        self.assertEqual(outcome, PushOutcome.REFUSED)
        self.sync_service.handle_push.assert_not_awaited()

    async def test_token_is_checked_without_the_bearer_prefix(self):
        await self._receive(_envelope({"emailAddress": "a@x.com", "historyId": 1}))

        self.auth_service.verify_google_token.assert_called_once_with("push-token")

    async def test_unreadable_envelopes_are_acked(self):
        for envelope in (
            None,
            {},
            {"message": {"data": "%%%"}},
            _envelope({"historyId": 1}),
            _envelope({"emailAddress": "a@x.com", "historyId": "not a number"}),
        ):
            with self.subTest(envelope=envelope):
                self.assertEqual(await self._receive(envelope), PushOutcome.ACK)
        self.sync_service.handle_push.assert_not_awaited()

    async def test_push_is_handed_over_lower_cased_with_an_int_history_id(self):
        outcome = await self._receive(
            _envelope({"emailAddress": "Purrf@Example.com", "historyId": "12345"})
        )

        self.assertEqual(outcome, PushOutcome.ACK)
        self.sync_service.handle_push.assert_awaited_once_with(
            self.session, "purrf@example.com", 12345
        )

    async def test_sync_outcome_is_returned_as_is(self):
        for sync_outcome in (PushOutcome.RETRY, PushOutcome.RESYNC):
            with self.subTest(sync_outcome=sync_outcome):
                self.sync_service.handle_push.return_value = sync_outcome

                outcome = await self._receive(
                    _envelope({"emailAddress": "a@x.com", "historyId": 1})
                )

                self.assertEqual(outcome, sync_outcome)

    async def test_unexpected_error_asks_for_a_retry(self):
        """Includes the IntegrityError two racing first-ever pushes can raise."""
        self.sync_service.handle_push.side_effect = RuntimeError("boom")

        outcome = await self._receive(
            _envelope({"emailAddress": "a@x.com", "historyId": 1})
        )

        self.assertEqual(outcome, PushOutcome.RETRY)
        self.logger.exception.assert_called_once()

    async def test_scheduled_resync_runs_on_its_own_session(self):
        await self.service.run_scheduled_resync()

        self.sync_service.run_scheduled_resync.assert_awaited_once_with(
            self.background_session
        )

    async def test_failed_scheduled_resync_is_logged_not_raised(self):
        self.sync_service.run_scheduled_resync.side_effect = RuntimeError("db down")

        await self.service.run_scheduled_resync()

        self.logger.exception.assert_called_once()


if __name__ == "__main__":
    unittest.main()
