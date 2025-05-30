from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from src.consumers.pubsub_puller import PubSubPuller, PullStatusResponse
from src.consumers.pubsub_pull_manager import check_pulling_status


class TestPubsubPullManager(TestCase):
    def setUp(self):
        self.valid_project_id = "test-project"
        self.valid_subscription_id = "test-subscription"
        self.mock_response = PullStatusResponse(
            subscription_id=self.valid_subscription_id,
            task_status="RUNNING",
            message="Test message",
            timestamp="2023-01-01T00:00:00Z",
        )

    @patch("src.consumers.pubsub_pull_manager.PubSubPuller")
    def test_successful_status_check(self, mock_puller):
        """Test successful status check with valid inputs."""
        mock_instance = mock_puller.return_value
        mock_instance.check_pulling_messages_status.return_value = self.mock_response

        result = check_pulling_status(self.valid_project_id, self.valid_subscription_id)

        mock_puller.assert_called_once_with(
            self.valid_project_id, self.valid_subscription_id
        )
        self.assertEqual(result, self.mock_response)

    @patch("src.consumers.pubsub_pull_manager.PubSubPuller")
    def test_empty_project_id(self, mock_puller):
        """Test ValueError when project_id is empty."""
        with self.assertRaises(ValueError) as context:
            check_pulling_status("", self.valid_subscription_id)

    @patch("src.consumers.pubsub_pull_manager.PubSubPuller")
    def test_none_project_id(self, mock_puller):
        """Test ValueError when project_id is None."""
        with self.assertRaises(ValueError) as context:
            check_pulling_status(None, self.valid_subscription_id)

    @patch("src.consumers.pubsub_pull_manager.PubSubPuller")
    def test_empty_subscription_id(self, mock_puller):
        """Test ValueError when subscription_id is empty."""
        with self.assertRaises(ValueError) as context:
            check_pulling_status(self.valid_project_id, "")

    @patch("src.consumers.pubsub_pull_manager.PubSubPuller")
    def test_none_subscription_id(self, mock_puller):
        """Test ValueError when subscription_id is None."""
        with self.assertRaises(ValueError) as context:
            check_pulling_status(self.valid_project_id, None)

    @patch("src.consumers.pubsub_pull_manager.PubSubPuller")
    def test_puller_exception_propagation(self, mock_puller):
        """Test that exceptions from PubSubPuller are propagated."""
        mock_instance = mock_puller.return_value
        mock_instance.check_pulling_messages_status.side_effect = RuntimeError(
            "Test error"
        )

        with self.assertRaises(RuntimeError) as context:
            check_pulling_status(self.valid_project_id, self.valid_subscription_id)
        self.assertEqual(str(context.exception), "Test error")


if __name__ == "__main__":
    main()
