import base64
import json
import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common.api_endpoints import NOTIFICATION_DELIVER_ENDPOINT
from backend.notification_management.delivery_controller import (
    NotificationDeliveryController,
)
from backend.notification_management.delivery_service import DeliveryOutcome


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


def _envelope(notification_id):
    data = base64.b64encode(json.dumps({"notification_id": notification_id}).encode())
    return {"message": {"data": data.decode()}}


class NotificationDeliveryControllerTest(unittest.TestCase):
    def setUp(self):
        self.delivery_service = AsyncMock()
        self.delivery_service.sweep_stragglers.return_value = []
        self.publisher = MagicMock()
        self.database = _FakeDatabase(AsyncMock())
        self.auth_service = MagicMock()
        self.auth_service.verify_google_token.return_value = {"sub": "111-pusher"}
        self.controller = NotificationDeliveryController(
            delivery_service=self.delivery_service,
            publisher=self.publisher,
            topic_path="projects/p/topics/notifications",
            database=self.database,
            auth_service=self.auth_service,
            pusher_subs=frozenset({"111-pusher"}),
        )
        app = FastAPI()
        app.include_router(self.controller.router)
        self.client = TestClient(app)

    def test_a_request_without_a_token_is_refused(self):
        """A person signed in to Access could otherwise force early delivery."""
        response = self.client.post(NOTIFICATION_DELIVER_ENDPOINT, json=_envelope(42))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.delivery_service.deliver.assert_not_awaited()

    def test_a_token_from_an_unknown_service_account_is_refused(self):
        """Any account can mint a token for this audience, so the
        signature alone says nothing about who is calling."""
        self.auth_service.verify_google_token.return_value = {"sub": "999-stranger"}

        response = self.client.post(
            NOTIFICATION_DELIVER_ENDPOINT, json=_envelope(42), headers=_PUSH_HEADERS
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.delivery_service.deliver.assert_not_awaited()

    def test_an_empty_allowlist_refuses_everything(self):
        """Unconfigured must mean closed: envFrom changes do not restart
        pods, so an image can run before the value exists."""
        controller = NotificationDeliveryController(
            delivery_service=self.delivery_service,
            publisher=self.publisher,
            topic_path="projects/p/topics/notifications",
            database=self.database,
            auth_service=self.auth_service,
            pusher_subs=frozenset(),
        )
        app = FastAPI()
        app.include_router(controller.router)

        response = TestClient(app).post(
            NOTIFICATION_DELIVER_ENDPOINT, json=_envelope(42), headers=_PUSH_HEADERS
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.delivery_service.deliver.assert_not_awaited()

    def test_unparseable_envelope_is_acked_not_retried(self):
        response = self.client.post(
            NOTIFICATION_DELIVER_ENDPOINT,
            json={"nonsense": True},
            headers=_PUSH_HEADERS,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.delivery_service.deliver.assert_not_awaited()

    def test_acked_outcome_returns_200(self):
        self.delivery_service.deliver.return_value = DeliveryOutcome.ACKED

        response = self.client.post(
            NOTIFICATION_DELIVER_ENDPOINT, json=_envelope(42), headers=_PUSH_HEADERS
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.delivery_service.deliver.assert_awaited_once_with(
            self.database.session_object, 42
        )

    def test_retry_outcome_returns_503(self):
        self.delivery_service.deliver.return_value = DeliveryOutcome.RETRY

        response = self.client.post(
            NOTIFICATION_DELIVER_ENDPOINT, json=_envelope(42), headers=_PUSH_HEADERS
        )

        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)

    def test_stragglers_are_republished(self):
        self.delivery_service.deliver.return_value = DeliveryOutcome.ACKED
        self.delivery_service.sweep_stragglers.return_value = [7, 8]

        self.client.post(
            NOTIFICATION_DELIVER_ENDPOINT, json=_envelope(42), headers=_PUSH_HEADERS
        )

        self.assertEqual(self.publisher.publish.call_count, 2)
        published_ids = {
            json.loads(call.args[1])["notification_id"]
            for call in self.publisher.publish.call_args_list
        }
        self.assertEqual(published_ids, {7, 8})
        for call in self.publisher.publish.call_args_list:
            self.assertEqual(call.args[0], "projects/p/topics/notifications")


if __name__ == "__main__":
    unittest.main()
