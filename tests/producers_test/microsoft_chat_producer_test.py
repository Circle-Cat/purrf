import unittest
from unittest.mock import patch, Mock
from http import HTTPStatus
import json
import redis.exceptions
from concurrent.futures import TimeoutError
from src.producers.microsoft_chat_producer import main
from src.producers.microsoft_chat_producer.main import (
    notification_webhook,
    _validate_payload,
    redis_client,
    publisher_client,
    logger,
)
import os


class TestNotificationWebhook(unittest.TestCase):
    def setUp(self):
        self.topic_path = "projects/test-project/topics/test-topic"
        self.client_state = "abc123"
        self.handshake = {"validationToken": "test-validation-token"}
        self.invalid_value_not_list = {"value": {"subscriptionId": "sub1"}}
        self.invalid_value_empty = {"value": []}
        self.invalid_missing_clientState = {
            "value": [
                {
                    "subscriptionId": "sub1",
                    "resourceData": {
                        "id": "msg1",
                        "changeType": "created",
                        "resource": "users/u1/messages/m1",
                        "tenantId": "tid",
                        "message": "test-message",
                    },
                }
            ]
        }
        self.valid_notofiction = {
            "value": [
                {
                    "subscriptionId": "sub1",
                    "clientState": self.client_state,
                    "resourceData": {
                        "id": "msg1",
                        "changeType": "created",
                        "resource": "users/u1/messages/m1",
                        "tenantId": "tid",
                        "message": "test-message",
                    },
                }
            ]
        }

    def make_request(self, args=None, json_data=None):
        request = Mock()
        request.args = args or {}
        request.get_json.return_value = json_data
        return request

    def test_validation_token_response(self):
        request = self.make_request(args=self.handshake)

        response, status = notification_webhook(request)

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(response, "test-validation-token")

    def test_none_json_body(self):
        request = self.make_request(json_data=None)

        response, status = notification_webhook(request)

        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    def test_invalid_json_body(self):
        request = self.make_request(json_data=self.invalid_value_not_list)

        response, status = notification_webhook(request)

        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    def test_empty_notification_value(self):
        request = self.make_request(json_data=self.invalid_value_empty)

        response, status = notification_webhook(request)

        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    @patch.dict(
        os.environ,
        {
            "PROJECT_ID": "test-project",
            "TOPIC_ID": "test-topic",
            "REDIS_HOST": "test-redis-host",
            "REDIS_PORT": "6379",
            "REDIS_PASSWORD": "test-redids-password",
        },
    )
    @patch("src.producers.microsoft_chat_producer.main.Redis")
    @patch.object(main, "redis_client", new=None)
    @patch.object(main, "publisher_client", new=None)
    def test_redis_not_initialized(self, mock_redis_cls):
        mock_redis_cls.return_value = None

        request = self.make_request(json_data=self.valid_notofiction)

        response, status = notification_webhook(request)

        self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)

    @patch.dict(
        os.environ,
        {
            "PROJECT_ID": "test-project",
            "TOPIC_ID": "test-topic",
            "REDIS_HOST": "test-redis-host",
            "REDIS_PORT": "6379",
            "REDIS_PASSWORD": "test-redids-password",
        },
    )
    @patch("src.producers.microsoft_chat_producer.main.Redis")
    @patch("src.producers.microsoft_chat_producer.main.PublisherClient")
    @patch.object(main, "redis_client", new=None)
    @patch.object(main, "publisher_client", new=None)
    def test_pubsub_not_initialized(self, mock_publisher, mock_redis_cls):
        mock_pipeline = Mock()
        mock_pipeline.get.return_value = None
        mock_pipeline.execute.return_value = [self.client_state]
        mock_redis_client = Mock()
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_redis_client.ping.return_value = True
        mock_redis_cls.return_value = mock_redis_client
        mock_publisher.return_value = None

        request = self.make_request(json_data=self.valid_notofiction)

        response, status = notification_webhook(request)

        self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)
        mock_pipeline.get.assert_called_once()
        mock_pipeline.execute.assert_called_once()
        mock_redis_client.ping.assert_called_once()
        mock_redis_client.pipeline.assert_called_once()
        mock_publisher.topic_path.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "PROJECT_ID": "test-project",
            "TOPIC_ID": "test-topic",
            "REDIS_HOST": "test-redis-host",
            "REDIS_PORT": "6379",
            "REDIS_PASSWORD": "test-redids-password",
        },
    )
    @patch("src.producers.microsoft_chat_producer.main.Redis")
    @patch("src.producers.microsoft_chat_producer.main.PublisherClient")
    @patch.object(main, "redis_client", new=None)
    @patch.object(main, "publisher_client", new=None)
    def test_successful_publish(self, mock_publisher_cls, mock_redis_cls):
        mock_pipeline = Mock()
        mock_pipeline.get.return_value = self.client_state
        mock_pipeline.execute.return_value = [self.client_state]

        mock_redis_client_instance = Mock()
        mock_redis_client_instance.pipeline.return_value = mock_pipeline
        mock_redis_client_instance.ping.return_value = True
        mock_redis_cls.return_value = mock_redis_client_instance

        mock_future = Mock()
        mock_future.result.return_value = "message-id-1"

        mock_publisher_client_instance = Mock()
        mock_publisher_client_instance.topic_path.return_value = self.topic_path
        mock_publisher_client_instance.publish.return_value = mock_future
        mock_publisher_cls.return_value = mock_publisher_client_instance

        request = self.make_request(json_data=self.valid_notofiction)

        response, status = notification_webhook(request)

        self.assertEqual(status, HTTPStatus.ACCEPTED)

        mock_redis_cls.assert_called_once()
        mock_redis_client_instance.ping.assert_called_once()
        mock_redis_client_instance.pipeline.assert_called_once()
        mock_pipeline.get.assert_called_once()
        mock_pipeline.execute.assert_called_once()

        mock_publisher_cls.assert_called_once()
        mock_publisher_client_instance.topic_path.assert_called_once()

        expected_message_data = json.dumps(self.valid_notofiction["value"][0]).encode(
            "utf-8"
        )
        mock_publisher_client_instance.publish.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=3)

    @patch.dict(
        os.environ,
        {
            "PROJECT_ID": "test-project",
            "TOPIC_ID": "test-topic",
            "REDIS_HOST": "test-redis-host",
            "REDIS_PORT": "6379",
            "REDIS_PASSWORD": "test-redids-password",
        },
    )
    @patch("src.producers.microsoft_chat_producer.main.Redis")
    @patch("src.producers.microsoft_chat_producer.main.PublisherClient")
    @patch.object(main, "redis_client", new=None)
    @patch.object(main, "publisher_client", new=None)
    def test_publish_timeout(self, mock_publisher_cls, mock_redis_cls):
        mock_pipeline = Mock()
        mock_pipeline.get.return_value = self.client_state
        mock_pipeline.execute.return_value = [self.client_state]
        mock_redis_client_instance = Mock()
        mock_redis_client_instance.pipeline.return_value = mock_pipeline
        mock_redis_client_instance.ping.return_value = True
        mock_redis_cls.return_value = mock_redis_client_instance

        mock_future = Mock()
        mock_future.result.side_effect = TimeoutError

        mock_publisher_client_instance = Mock()
        mock_publisher_client_instance.topic_path.return_value = self.topic_path
        mock_publisher_client_instance.publish.return_value = mock_future
        mock_publisher_cls.return_value = mock_publisher_client_instance

        request = self.make_request(json_data=self.valid_notofiction)

        response, status = notification_webhook(request)

        self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)

        mock_redis_cls.assert_called_once()
        mock_redis_client_instance.ping.assert_called_once()
        mock_redis_client_instance.pipeline.assert_called_once()
        mock_pipeline.get.assert_called_once()
        mock_pipeline.execute.assert_called_once()

        mock_publisher_cls.assert_called_once()
        mock_publisher_client_instance.topic_path.assert_called_once()

        expected_message_data = json.dumps(self.valid_notofiction["value"][0]).encode(
            "utf-8"
        )
        mock_publisher_client_instance.publish.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=3)


class TestValidatePayload(unittest.TestCase):
    def setUp(self):
        self.mock_logger_error = patch.object(logger, "error").start()
        self.test_cases = [
            {
                "name": "valid payload",
                "payload": {
                    "subscriptionId": "sub123",
                    "clientState": "state456",
                    "resourceData": {"id": "data789"},
                },
                "expected_is_valid": True,
                "expected_log_message": None,
            },
            {
                "name": "payload is not a dict",
                "payload": "invalid_string",
                "expected_is_valid": False,
                "expected_log_message": "Payload must be a JSON object.",
            },
            {
                "name": "missing subscriptionId field",
                "payload": {
                    "clientState": "state456",
                    "resourceData": {"id": "data789"},
                },
                "expected_is_valid": False,
                "expected_log_message": "Missing required field: subscriptionId",
            },
            {
                "name": "missing clientState field",
                "payload": {
                    "subscriptionId": "sub123",
                    "resourceData": {"id": "data789"},
                },
                "expected_is_valid": False,
                "expected_log_message": "Missing required field: clientState",
            },
            {
                "name": "missing resourceData field",
                "payload": {"subscriptionId": "sub123", "clientState": "state456"},
                "expected_is_valid": False,
                "expected_log_message": "Missing required field: resourceData",
            },
            {
                "name": "empty string for subscriptionId",
                "payload": {
                    "subscriptionId": "",
                    "clientState": "state456",
                    "resourceData": {"id": "data789"},
                },
                "expected_is_valid": False,
                "expected_log_message": "Field 'subscriptionId' must not be empty or None.",
            },
            {
                "name": "None for clientState",
                "payload": {
                    "subscriptionId": "sub123",
                    "clientState": None,
                    "resourceData": {"id": "data789"},
                },
                "expected_is_valid": False,
                "expected_log_message": "Field 'clientState' must not be empty or None.",
            },
            {
                "name": "empty dict for resourceData",
                "payload": {
                    "subscriptionId": "sub123",
                    "clientState": "state456",
                    "resourceData": {},
                },
                "expected_is_valid": False,
                "expected_log_message": "Field 'resourceData' must not be empty or None.",
            },
            {
                "name": "None for resourceData",
                "payload": {
                    "subscriptionId": "sub123",
                    "clientState": "state456",
                    "resourceData": None,
                },
                "expected_is_valid": False,
                "expected_log_message": "Field 'resourceData' must not be empty or None.",
            },
        ]

    def test_validate_payload_scenarios(self):
        """
        Tests various scenarios for _validate_payload function using a data-driven approach.
        """
        for case in self.test_cases:
            with self.subTest(msg=case["name"]):
                self.mock_logger_error.reset_mock()

                is_valid = _validate_payload(case["payload"])
                self.assertEqual(is_valid, case["expected_is_valid"])

                if case["expected_log_message"]:
                    self.mock_logger_error.assert_called_once_with(
                        case["expected_log_message"]
                    )
                else:
                    self.mock_logger_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
