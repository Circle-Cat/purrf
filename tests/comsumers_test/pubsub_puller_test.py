from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from src.consumers.pubsub_puller import PubSubPuller, PullStatusResponse
from src.common.constants import PullStatus, PUBSUB_PULL_MESSAGES_STATUS_KEY


class TestPubSubPuller(TestCase):
    def setUp(self):
        PubSubPuller._instances = {}
        self.project_id = "test-project"
        self.subscription_id = "test-subscription"

    def test_singleton_pattern(self):
        """Verify that PubSubPuller maintains single instance per (project, subscription) pair."""
        puller1 = PubSubPuller(self.project_id, self.subscription_id)
        puller2 = PubSubPuller(self.project_id, self.subscription_id)

        self.assertIs(puller1, puller2)

        puller3 = PubSubPuller("another-project", "test-subscription")

        self.assertIsNot(puller1, puller3)

    @patch("src.consumers.pubsub_puller.RedisClientFactory")
    def test_redis_client_unavailable(self, mock_factory):
        """Test proper error when Redis client cannot be created."""
        mock_factory().create_redis_client.return_value = None

        puller = PubSubPuller(self.project_id, self.subscription_id)

        with self.assertRaises(ValueError) as context:
            puller.check_pulling_messages_status()

        self.assertIn("Redis client not available", str(context.exception))

    @patch("src.consumers.pubsub_puller.RedisClientFactory")
    def test_redis_status_not_found_and_not_pulling(self, mock_factory):
        """Test correct NOT_STARTED response when no Redis status found and not pulling locally."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {}
        mock_factory().create_redis_client.return_value = redis_client

        expected_result = PullStatusResponse(
            subscription_id=self.subscription_id,
            task_status=PullStatus.NOT_STARTED.code,
            message=PullStatus.NOT_STARTED.format_message(
                subscription_id=self.subscription_id
            ),
            timestamp=None,
        )

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.clear()
        puller._streaming_pull_future = None

        result = puller.check_pulling_messages_status()

        self.assertEqual(expected_result, result)

    @patch("src.consumers.pubsub_puller.RedisClientFactory")
    def test_redis_status_not_found_but_local_is_pulling(self, mock_factory):
        """Test inconsistency error when locally pulling but no Redis status exists."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {}
        mock_factory().create_redis_client.return_value = redis_client
        mock_future = MagicMock()
        mock_future.done.return_value = False

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.set()
        puller._streaming_pull_future = mock_future

        with self.assertRaises(RuntimeError) as context:
            puller.check_pulling_messages_status()

        self.assertIn("Status inconsistency", str(context.exception))

    @patch("src.consumers.pubsub_puller.RedisClientFactory")
    def test_redis_running_but_local_not_pulling(self, mock_factory):
        """Test inconsistency error when Redis reports running but locally not pulling."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {
            "task_status": PullStatus.RUNNING.code,
            "timestamp": "2024-05-28T12:00:00Z",
            "message": "Running normally",
        }
        mock_factory().create_redis_client.return_value = redis_client

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.clear()
        puller._streaming_pull_future = None

        with self.assertRaises(RuntimeError) as context:
            puller.check_pulling_messages_status()

        self.assertIn("Status inconsistency", str(context.exception))

    @patch("src.consumers.pubsub_puller.RedisClientFactory")
    def test_local_pulling_but_redis_not_running(self, mock_factory):
        """Test inconsistency error when locally pulling but Redis reports stopped."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {
            "task_status": PullStatus.STOPPED.code,
            "timestamp": "2024-05-28T12:00:00Z",
            "message": "Stopped",
        }
        mock_factory().create_redis_client.return_value = redis_client
        mock_future = MagicMock()
        mock_future.done.return_value = False

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.set()
        puller._streaming_pull_future = mock_future

        with self.assertRaises(RuntimeError) as context:
            puller.check_pulling_messages_status()

        self.assertIn("Status inconsistency", str(context.exception))

    @patch("src.consumers.pubsub_puller.RedisClientFactory")
    def test_status_consistent_running(self, mock_factory):
        """Test successful status check when local and Redis states match (RUNNING)."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {
            "task_status": PullStatus.RUNNING.code,
            "timestamp": "2024-05-28T12:00:00Z",
            "message": PullStatus.RUNNING.format_message(
                subscription_id=self.subscription_id
            ),
        }
        expected_result = PullStatusResponse(
            subscription_id=self.subscription_id,
            task_status=PullStatus.RUNNING.code,
            message=PullStatus.RUNNING.format_message(
                subscription_id=self.subscription_id
            ),
            timestamp="2024-05-28T12:00:00Z",
        )

        mock_factory().create_redis_client.return_value = redis_client
        mock_future = MagicMock()
        mock_future.done.return_value = False

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.set()
        puller._streaming_pull_future = mock_future

        result = puller.check_pulling_messages_status()
        self.assertEqual(expected_result, result)


if __name__ == "__main__":
    main()
