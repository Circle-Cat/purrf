from http import HTTPStatus
from unittest import TestCase, main, IsolatedAsyncioTestCase
from unittest.mock import patch, MagicMock
from flask import Flask
from backend.consumers.consumer_controller import consumers_bp, ConsumerController


PUBSUB_PULL_STATUS_CHECK_API = "/api/pubsub/pull/status/{project_id}/{subscription_id}"
PUBSUB_PULL_STATUS_STOP_API = "/api/pubsub/pull/{project_id}/{subscription_id}"
START_GOOGLE_PULLING_API = "/api/google/chat/pull/{project_id}/{subscription_id}"
TEST_PROJECT_ID = "test-project"
TEST_SUBSCRIPTION_ID = "test-subscription"


class TestConsumerController(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.microsoft_message_processor_service = MagicMock()
        self.controller = ConsumerController(
            microsoft_message_processor_service=self.microsoft_message_processor_service,
        )

        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

    async def asyncTearDown(self):
        self.app_context.pop()

    async def test_all_microsoft_chat_topics(self):
        response = self.controller.start_microsoft_pulling(
            TEST_PROJECT_ID, TEST_SUBSCRIPTION_ID
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], {})
        self.microsoft_message_processor_service.pull_microsoft_message.assert_called_once()


class TestAppRoutes(TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(consumers_bp)
        self.client = app.test_client()
        app.testing = True

    @patch("backend.consumers.consumer_controller.check_pulling_status")
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

    @patch("backend.consumers.consumer_controller.stop_pulling_process")
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

    @patch("backend.consumers.consumer_controller.pull_messages")
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
