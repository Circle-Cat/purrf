import base64
import json
import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common.api_endpoints import GMAIL_PUSH_ENDPOINT
from backend.communication.gmail_push_controller import GmailPushController
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


_PUSH_HEADERS = {"Authorization": "Bearer push-token"}


def _envelope(payload):
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": data, "messageId": "1"}, "subscription": "s"}


class GmailPushControllerTest(unittest.TestCase):
    def setUp(self):
        self.sync_service = AsyncMock()
        self.sync_service.handle_push.return_value = PushOutcome.ACK
        self.session = AsyncMock()
        self.auth_service = MagicMock()
        self.auth_service.verify_google_token.return_value = {"sub": "111-pusher"}
        self.logger = MagicMock()
        self.client = self._client(frozenset({"111-pusher"}))

    def _client(self, pusher_subs):
        controller = GmailPushController(
            logger=self.logger,
            gmail_sync_service=self.sync_service,
            database=_FakeDatabase(self.session),
            auth_service=self.auth_service,
            pusher_subs=pusher_subs,
        )
        app = FastAPI()
        app.include_router(controller.router)
        return TestClient(app)

    def _post(self, body, headers=_PUSH_HEADERS):
        return self.client.post(GMAIL_PUSH_ENDPOINT, json=body, headers=headers)

    def test_missing_bearer_is_forbidden(self):
        response = self._post(_envelope({}), headers={})

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.sync_service.handle_push.assert_not_awaited()

    def test_unverifiable_token_is_forbidden(self):
        self.auth_service.verify_google_token.side_effect = ValueError("expired")

        response = self._post(_envelope({}))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.sync_service.handle_push.assert_not_awaited()

    def test_unknown_sub_is_forbidden(self):
        self.auth_service.verify_google_token.return_value = {"sub": "other"}

        response = self._post(_envelope({}))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.sync_service.handle_push.assert_not_awaited()

    def test_empty_allowlist_refuses_everyone(self):
        self.client = self._client(frozenset())

        response = self._post(_envelope({}))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.sync_service.handle_push.assert_not_awaited()

    def test_unreadable_envelope_is_acked(self):
        response = self._post({"message": {"data": "%%%"}})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.sync_service.handle_push.assert_not_awaited()

    def test_push_is_handed_over_with_an_int_history_id(self):
        response = self._post(
            _envelope({"emailAddress": "Purrf@Example.com", "historyId": "12345"})
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.sync_service.handle_push.assert_awaited_once_with(
            self.session, "purrf@example.com", 12345
        )

    def test_retry_outcome_is_503(self):
        self.sync_service.handle_push.return_value = PushOutcome.RETRY

        response = self._post(
            _envelope({"emailAddress": "purrf@example.com", "historyId": 1})
        )

        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)

    def test_resync_outcome_is_200_and_runs_the_resync_after_the_response(self):
        self.sync_service.handle_push.return_value = PushOutcome.RESYNC

        response = self._post(
            _envelope({"emailAddress": "purrf@example.com", "historyId": 1})
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.sync_service.run_scheduled_resync.assert_awaited_once_with(self.session)

    def test_ack_outcome_does_not_start_a_resync(self):
        self._post(_envelope({"emailAddress": "purrf@example.com", "historyId": 1}))

        self.sync_service.run_scheduled_resync.assert_not_awaited()

    def test_failed_background_resync_is_logged_and_the_push_stays_acked(self):
        self.sync_service.handle_push.return_value = PushOutcome.RESYNC
        self.sync_service.run_scheduled_resync.side_effect = RuntimeError("db down")

        response = self._post(
            _envelope({"emailAddress": "purrf@example.com", "historyId": 1})
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.logger.exception.assert_called_once()

    def test_unexpected_error_is_503(self):
        """Includes the IntegrityError two racing first-ever pushes can raise."""
        self.sync_service.handle_push.side_effect = RuntimeError("boom")

        response = self._post(
            _envelope({"emailAddress": "purrf@example.com", "historyId": 1})
        )

        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
