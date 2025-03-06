from unittest import TestCase, main
from unittest.mock import Mock, patch
import logging
from io import StringIO
from google.pubsub_publisher import (
    create_subscription,
    create_pubsub_topic,
    create_workspaces_subscriptions,
)

TEST_PROJECT_ID = "test-project"
TEST_TOPIC_ID = "test-topic"
TEST_SUBSCRIPTION_ID = "test-subscription"
TEST_SPACE_ID = "test-space"
TEST_EVENT_TYPES = ["google.workspace.chat.message.v1.created"]
EXPECTED_TOPIC_PATH = f"projects/{TEST_PROJECT_ID}/topics/{TEST_TOPIC_ID}"
EXPECTED_SUBSCRIPTION_PATH = (
    f"projects/{TEST_PROJECT_ID}/subscriptions/{TEST_SUBSCRIPTION_ID}"
)
EXPECTED_TOPIC = "test-topic"


class TestPubsubPublisher(TestCase):
    @patch("google.pubsub_publisher.GoogleClientFactory")
    def test_create_pubsub_topic_success(self, mock_client_factory):
        mock_publisher = Mock()
        mock_publisher.topic_path.return_value = EXPECTED_TOPIC_PATH
        mock_publisher.create_topic.return_value = EXPECTED_TOPIC

        mock_factory_instance = Mock()
        mock_factory_instance.create_publisher_client.return_value = mock_publisher
        mock_client_factory.return_value = mock_factory_instance

        result = create_pubsub_topic(TEST_PROJECT_ID, TEST_TOPIC_ID)

        self.assertEqual(result, EXPECTED_TOPIC)

        mock_publisher.topic_path.assert_called_once_with(
            TEST_PROJECT_ID, TEST_TOPIC_ID
        )
        mock_publisher.create_topic.assert_called_once_with(name=EXPECTED_TOPIC_PATH)

    @patch("google.pubsub_publisher.GoogleClientFactory")
    def test_create_workspaces_subscriptions_success(self, mock_client_factory):
        mock_workspaceevents = Mock()
        mock_subscriptions = Mock()
        mock_execute = Mock(return_value={"subscription_id": "test-subscription"})

        mock_subscriptions.create.return_value.execute = mock_execute
        mock_workspaceevents.subscriptions.return_value = mock_subscriptions

        mock_factory_instance = Mock()
        mock_factory_instance.create_workspaceevents_client.return_value = (
            mock_workspaceevents
        )
        mock_client_factory.return_value = mock_factory_instance

        response = create_workspaces_subscriptions(
            TEST_PROJECT_ID, TEST_TOPIC_ID, TEST_SPACE_ID, TEST_EVENT_TYPES
        )

        expected_body = {
            "target_resource": f"//chat.googleapis.com/spaces/{TEST_SPACE_ID}",
            "event_types": TEST_EVENT_TYPES,
            "notification_endpoint": {
                "pubsub_topic": f"projects/{TEST_PROJECT_ID}/topics/{TEST_TOPIC_ID}"
            },
            "payload_options": {"include_resource": True},
        }

        mock_subscriptions.create.assert_called_once_with(body=expected_body)
        mock_execute.assert_called_once()
        self.assertEqual(response, {"subscription_id": "test-subscription"})

    @patch("google.pubsub_publisher.GoogleClientFactory")
    def test_create_subscription_success(self, mock_client_factory):
        mock_subscriber = Mock()
        mock_subscriber.topic_path.return_value = EXPECTED_TOPIC_PATH
        mock_subscriber.subscription_path.return_value = EXPECTED_SUBSCRIPTION_PATH

        mock_factory_instance = Mock()
        mock_factory_instance.create_subscriber_client.return_value = mock_subscriber
        mock_client_factory.return_value = mock_factory_instance

        result = create_subscription(
            TEST_PROJECT_ID, TEST_TOPIC_ID, TEST_SUBSCRIPTION_ID
        )

        self.assertEqual(result, EXPECTED_SUBSCRIPTION_PATH)

        mock_subscriber.topic_path.assert_called_once_with(
            TEST_PROJECT_ID, TEST_TOPIC_ID
        )
        mock_subscriber.subscription_path.assert_called_once_with(
            TEST_PROJECT_ID, TEST_SUBSCRIPTION_ID
        )

        expected_request = {
            "name": EXPECTED_SUBSCRIPTION_PATH,
            "topic": EXPECTED_TOPIC_PATH,
            "expiration_policy": {},
        }
        mock_subscriber.create_subscription.assert_called_once_with(
            request=expected_request
        )


if __name__ == "__main__":
    main()
