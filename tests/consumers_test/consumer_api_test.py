from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import patch
from flask import Flask
from src.consumers.consumer_api import consumers_bp


PUBSUB_PULL_STATUS_CHECK_API = "/api/pubsub/pull/status/{project_id}/{subscription_id}"
PUBSUB_PULL_STATUS_STOP_API = "/api/pubsub/pull/{project_id}/{subscription_id}"
START_MICROSOFT_PULLING_API = "/api/microsoft/pull/{project_id}/{subscription_id}"
START_GOOGLE_PULLING_API = "/api/google/chat/pull/{project_id}/{subscription_id}"
TEST_PROJECT_ID = "test-project"
TEST_SUBSCRIPTION_ID = "test-subscription"


class TestAppRoutes(TestCase):
    @classmethod
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(consumers_bp)
        self.client = app.test_client()
        app.testing = True

    @patch("src.consumers.consumer_api.check_pulling_status")
    def test_check_pulling_messages(self, mock_check_pulling_status):
        mock_result = {}
        mock_check_pulling_status.return_value = mock_result

        response = self.client.get(
            PUBSUB_PULL_STATUS_CHECK_API.format(
                project_id=TEST_PROJECT_ID, subscription_id=TEST_SUBSCRIPTION_ID
            )
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)

        mock_check_pulling_status.assert_called_once_with(
            TEST_PROJECT_ID, TEST_SUBSCRIPTION_ID
        )

    @patch("src.consumers.consumer_api.stop_pulling_process")
    def test_stop_pulling(self, mock_stop_pulling):
        mock_result = {}
        mock_stop_pulling.return_value = mock_result

        response = self.client.delete(
            PUBSUB_PULL_STATUS_STOP_API.format(
                project_id=TEST_PROJECT_ID, subscription_id=TEST_SUBSCRIPTION_ID
            )
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)

        mock_stop_pulling.assert_called_once_with(TEST_PROJECT_ID, TEST_SUBSCRIPTION_ID)

    @patch("src.consumers.consumer_api.pull_microsoft_message")
    def test_start_microsoft_pulling(self, mock_start_pulling):
        mock_result = {}
        mock_start_pulling.return_value = mock_result

        response = self.client.post(
            START_MICROSOFT_PULLING_API.format(
                project_id=TEST_PROJECT_ID, subscription_id=TEST_SUBSCRIPTION_ID
            )
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)

        mock_start_pulling.assert_called_once_with(
            TEST_PROJECT_ID, TEST_SUBSCRIPTION_ID
        )

    @patch("src.consumers.consumer_api.pull_messages")
    def test_start_google_pull(self, mock_pull_messages):
        mock_pull_messages.return_value = None
        response = self.client.post(
            START_GOOGLE_PULLING_API.format(
                project_id=TEST_PROJECT_ID, subscription_id=TEST_SUBSCRIPTION_ID
            )
        )

        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)

        body = response.get_json()
        expected_msg = (
            f"Started pulling google chat messages for subscription "
            f"'{TEST_SUBSCRIPTION_ID}' in project '{TEST_PROJECT_ID}'."
        )
        self.assertEqual(body.get("message"), expected_msg)
        self.assertEqual(body.get("data"), {})

        mock_pull_messages.assert_called_once_with(
            TEST_PROJECT_ID, TEST_SUBSCRIPTION_ID
        )


if __name__ == "__main__":
    main()
