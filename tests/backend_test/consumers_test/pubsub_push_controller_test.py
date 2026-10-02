import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common.api_endpoints import (
    PUBSUB_PUSH_GERRIT_ENDPOINT,
    PUBSUB_PUSH_GOOGLE_CHAT_ENDPOINT,
)
from backend.consumers.pubsub_push_controller import PubSubPushController
from backend.consumers.pubsub_push_service import PubSubPushOutcome


class PubSubPushControllerTest(unittest.TestCase):
    def setUp(self):
        self.push_service = AsyncMock()
        self.push_service.receive_google_chat.return_value = PubSubPushOutcome.ACK
        self.push_service.receive_gerrit.return_value = PubSubPushOutcome.ACK
        controller = PubSubPushController(pubsub_push_service=self.push_service)
        app = FastAPI()
        app.include_router(controller.router)
        self.client = TestClient(app)

    def test_each_endpoint_reaches_its_own_handler(self):
        chat_body = {"message": {"data": "chat"}}
        gerrit_body = {"message": {"data": "gerrit"}}

        self.client.post(
            PUBSUB_PUSH_GOOGLE_CHAT_ENDPOINT,
            json=chat_body,
            headers={"Authorization": "Bearer chat-token"},
        )
        self.client.post(
            PUBSUB_PUSH_GERRIT_ENDPOINT,
            json=gerrit_body,
            headers={"Authorization": "Bearer gerrit-token"},
        )

        self.push_service.receive_google_chat.assert_awaited_once_with(
            "Bearer chat-token", chat_body
        )
        self.push_service.receive_gerrit.assert_awaited_once_with(
            "Bearer gerrit-token", gerrit_body
        )

    def test_missing_header_is_handed_over_as_empty(self):
        self.client.post(PUBSUB_PUSH_GERRIT_ENDPOINT, json={})

        self.push_service.receive_gerrit.assert_awaited_once_with("", {})

    def test_body_that_is_not_json_is_handed_over_as_none(self):
        self.client.post(PUBSUB_PUSH_GOOGLE_CHAT_ENDPOINT, content=b"not json")

        self.push_service.receive_google_chat.assert_awaited_once_with("", None)

    def test_outcome_maps_to_status(self):
        for endpoint, method in (
            (PUBSUB_PUSH_GOOGLE_CHAT_ENDPOINT, self.push_service.receive_google_chat),
            (PUBSUB_PUSH_GERRIT_ENDPOINT, self.push_service.receive_gerrit),
        ):
            for outcome, status in (
                (PubSubPushOutcome.ACK, HTTPStatus.OK),
                (PubSubPushOutcome.RETRY, HTTPStatus.SERVICE_UNAVAILABLE),
                (PubSubPushOutcome.REFUSED, HTTPStatus.FORBIDDEN),
            ):
                with self.subTest(endpoint=endpoint, outcome=outcome):
                    method.return_value = outcome

                    response = self.client.post(endpoint, json={})

                    self.assertEqual(response.status_code, status)


if __name__ == "__main__":
    unittest.main()
