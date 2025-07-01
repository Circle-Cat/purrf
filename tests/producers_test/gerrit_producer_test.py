import os
import json
import unittest
from unittest.mock import patch, Mock
from http import HTTPStatus
from src.producers.gerrit_producer import main
from src.producers.gerrit_producer.main import (
    gerrit_event_webhook,
    publisher_client,
)


class TestGerritEventWebhook(unittest.TestCase):
    def setUp(self):
        self.sample_payload = {
            "type": "change-merged",
            "change": {
                "_number": 123456,
                "project": "purrf",
                "owner": {"username": "bkuang3"},
                "insertions": 120,
                "created": "2025-06-17 10:20:00.000000",
            },
            "eventCreatedOn": 1718625600,
        }

        self.topic_path = "projects/test-project/topics/test-topic"

        main.publisher_client = None

    def make_request(self, json_data=None, headers=None):
        request = Mock()
        request.get_json.return_value = json_data
        request.headers = headers or {}
        return request

    def test_empty_payload_returns_400(self):
        request = self.make_request(json_data={})
        response, status = gerrit_event_webhook(request)
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertIn("Empty payload", response)

    def test_invalid_json_returns_400(self):
        request = Mock()
        request.get_json.side_effect = Exception("Bad JSON")
        request.headers = {}
        response, status = gerrit_event_webhook(request)
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertIn("Invalid JSON", response)

    @patch.dict(
        os.environ,
        {
            "PROJECT_ID": "test-project",
            "TOPIC_ID": "test-topic",
        },
    )
    @patch("src.producers.gerrit_producer.main.EXPECTED_SECRET", new="expected-secret")
    @patch("src.producers.gerrit_producer.main.PublisherClient")
    @patch.object(main, "publisher_client", new=None)
    def test_invalid_secret_returns_401(self, mock_pubsub_client):
        request = self.make_request(
            json_data=self.sample_payload,
            headers={"X-Gerrit-Webhook-Secret": "wrong-secret"},
        )
        response, status = gerrit_event_webhook(request)
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)
        self.assertIn("Unauthorized", response)

    @patch.dict(os.environ, {"PROJECT_ID": "test-project", "TOPIC_ID": "test-topic"})
    @patch("src.producers.gerrit_producer.main.PublisherClient")
    def test_successful_publish(self, mock_pubsub_cls):
        mock_future = Mock()
        mock_future.result.return_value = "mock-message-id"

        mock_pubsub_instance = Mock()
        mock_pubsub_instance.publish.return_value = mock_future
        mock_pubsub_instance.topic_path.return_value = self.topic_path
        mock_pubsub_cls.return_value = mock_pubsub_instance

        request = self.make_request(json_data=self.sample_payload)
        response, status = gerrit_event_webhook(request)

        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("Gerrit Event published", response)
        mock_pubsub_instance.publish.assert_called_once()

    @patch.dict(os.environ, {"PROJECT_ID": "test-project", "TOPIC_ID": "test-topic"})
    @patch("src.producers.gerrit_producer.main.PublisherClient")
    def test_publish_timeout_returns_500(self, mock_pubsub_cls):
        mock_future = Mock()
        mock_future.result.side_effect = TimeoutError

        mock_pubsub_instance = Mock()
        mock_pubsub_instance.publish.return_value = mock_future
        mock_pubsub_instance.topic_path.return_value = self.topic_path
        mock_pubsub_cls.return_value = mock_pubsub_instance

        request = self.make_request(json_data=self.sample_payload)
        response, status = gerrit_event_webhook(request)

        self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIn("Failed to publish", response)


if __name__ == "__main__":
    unittest.main()
