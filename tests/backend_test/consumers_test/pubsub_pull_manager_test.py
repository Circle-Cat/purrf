from unittest import TestCase, main
from unittest.mock import MagicMock
from backend.consumers.pubsub_puller import PullStatusResponse
from backend.consumers.pubsub_pull_manager import PubSubPullManager


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

        self.mock_puller = MagicMock()
        self.mock_puller.check_pulling_messages_status.return_value = self.mock_response
        self.mock_puller.stop_pulling_messages.return_value = self.mock_response

        self.mock_factory = MagicMock()
        self.mock_factory.get_puller_instance.return_value = self.mock_puller

        self.manager = PubSubPullManager(pubsub_puller_factory=self.mock_factory)

    def test_successful_status_check(self):
        """Test successful status check with valid inputs."""
        result = self.manager.check_pulling_status(
            self.valid_project_id, self.valid_subscription_id
        )

        self.mock_factory.get_puller_instance.assert_called_once_with(
            self.valid_project_id, self.valid_subscription_id
        )
        self.mock_puller.check_pulling_messages_status.assert_called_once()
        self.assertEqual(result, self.mock_response)

    def test_empty_project_id(self):
        """Test ValueError when project_id is empty."""
        with self.assertRaises(ValueError):
            self.manager.check_pulling_status("", self.valid_subscription_id)

    def test_none_project_id(self):
        """Test ValueError when project_id is None."""
        with self.assertRaises(ValueError):
            self.manager.check_pulling_status(None, self.valid_subscription_id)

    def test_empty_subscription_id(self):
        """Test ValueError when subscription_id is empty."""
        with self.assertRaises(ValueError):
            self.manager.check_pulling_status(self.valid_project_id, "")

    def test_none_subscription_id(self):
        """Test ValueError when subscription_id is None."""
        with self.assertRaises(ValueError):
            self.manager.check_pulling_status(self.valid_project_id, None)

    def test_puller_exception_propagation(self):
        """Test that exceptions from PubSubPuller are propagated."""
        self.mock_puller.check_pulling_messages_status.side_effect = RuntimeError(
            "Test error"
        )

        with self.assertRaises(RuntimeError) as context:
            self.manager.check_pulling_status(
                self.valid_project_id, self.valid_subscription_id
            )
        self.assertEqual(str(context.exception), "Test error")

    def test_successful_stop_pulling_process(self):
        """Test successful stop of pulling process."""
        self.mock_puller.stop_pulling_messages.return_value = self.mock_response

        result = self.manager.stop_pulling_process(
            self.valid_project_id, self.valid_subscription_id
        )

        self.mock_factory.get_puller_instance.assert_called_once_with(
            self.valid_project_id, self.valid_subscription_id
        )
        self.mock_puller.stop_pulling_messages.assert_called_once()
        self.assertEqual(result, self.mock_response)

    def test_stop_empty_project_id(self):
        """Test ValueError when stopping with empty project_id."""
        with self.assertRaises(ValueError):
            self.manager.stop_pulling_process("", self.valid_subscription_id)

    def test_stop_empty_subscription_id(self):
        """Test ValueError when stopping with empty subscription_id."""
        with self.assertRaises(ValueError):
            self.manager.stop_pulling_process(self.valid_project_id, "")

    def test_stop_pulling_process_raises_exception(self):
        """Test exception propagation from stop_pulling_messages."""
        self.mock_puller.stop_pulling_messages.side_effect = RuntimeError(
            "Stopping failed"
        )

        with self.assertRaises(RuntimeError) as context:
            self.manager.stop_pulling_process(
                self.valid_project_id, self.valid_subscription_id
            )
        self.assertEqual(str(context.exception), "Stopping failed")


if __name__ == "__main__":
    main()
