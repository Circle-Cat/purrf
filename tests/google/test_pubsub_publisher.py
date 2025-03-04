from unittest import TestCase, main
from unittest.mock import Mock, patch
import logging
from io import StringIO
from google.pubsub_publisher import create_subscription

TEST_PROJECT_ID = "test-project"
TEST_TOPIC_ID = "test-topic"
TEST_SUBSCRIPTION_ID = "test-subscription"
EXPECTED_TOPIC_PATH = f"projects/{TEST_PROJECT_ID}/topics/{TEST_TOPIC_ID}"
EXPECTED_SUBSCRIPTION_PATH = (
    f"projects/{TEST_PROJECT_ID}/subscriptions/{TEST_SUBSCRIPTION_ID}"
)


class TestPubsubPublisher(TestCase):
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
