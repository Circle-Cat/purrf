import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock

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


class GmailPushControllerTest(unittest.TestCase):
    def setUp(self):
        self.push_service = AsyncMock()
        self.push_service.receive.return_value = PushOutcome.ACK
        self.session = AsyncMock()
        controller = GmailPushController(
            gmail_push_service=self.push_service,
            database=_FakeDatabase(self.session),
        )
        app = FastAPI()
        app.include_router(controller.router)
        self.client = TestClient(app)

    def test_header_and_body_are_handed_over(self):
        body = {"message": {"data": "abc"}}

        self.client.post(
            GMAIL_PUSH_ENDPOINT, json=body, headers={"Authorization": "Bearer t"}
        )

        self.push_service.receive.assert_awaited_once_with(
            self.session, "Bearer t", body
        )

    def test_missing_header_is_handed_over_as_empty(self):
        self.client.post(GMAIL_PUSH_ENDPOINT, json={})

        self.push_service.receive.assert_awaited_once_with(self.session, "", {})

    def test_body_that_is_not_json_is_handed_over_as_none(self):
        self.client.post(GMAIL_PUSH_ENDPOINT, content=b"not json")

        self.push_service.receive.assert_awaited_once_with(self.session, "", None)

    def test_outcome_maps_to_status(self):
        for outcome, status in (
            (PushOutcome.ACK, HTTPStatus.OK),
            (PushOutcome.RESYNC, HTTPStatus.OK),
            (PushOutcome.RETRY, HTTPStatus.SERVICE_UNAVAILABLE),
            (PushOutcome.REFUSED, HTTPStatus.FORBIDDEN),
        ):
            with self.subTest(outcome=outcome):
                self.push_service.receive.return_value = outcome

                response = self.client.post(GMAIL_PUSH_ENDPOINT, json={})

                self.assertEqual(response.status_code, status)

    def test_resync_outcome_runs_the_resync_after_the_response(self):
        self.push_service.receive.return_value = PushOutcome.RESYNC

        self.client.post(GMAIL_PUSH_ENDPOINT, json={})

        self.push_service.run_scheduled_resync.assert_awaited_once_with()

    def test_other_outcomes_do_not_start_a_resync(self):
        for outcome in (PushOutcome.ACK, PushOutcome.RETRY, PushOutcome.REFUSED):
            with self.subTest(outcome=outcome):
                self.push_service.receive.return_value = outcome

                self.client.post(GMAIL_PUSH_ENDPOINT, json={})

        self.push_service.run_scheduled_resync.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
