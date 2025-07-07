from unittest import TestCase, main
from unittest.mock import Mock, patch
from src.notification_management.google_chat_watcher import (
    create_workspaces_subscriptions,
)

TEST_PROJECT_ID = "test-project"
TEST_TOPIC_ID = "test-topic"
TEST_SPACE_ID = "test-space"
TEST_EVENT_TYPES = ["google.workspace.chat.message.v1.created"]


class TestPubsubPublisher(TestCase):
    @patch("src.notification_management.google_chat_watcher.GoogleClientFactory")
    def test_create_workspaces_subscriptions_success(self, mock_factory_cls):
        mock_subscriptions = Mock()
        mock_create = Mock()
        mock_create.execute.return_value = {"subscription_id": "test-subscription"}
        mock_subscriptions.create.return_value = mock_create

        mock_workspace_client = Mock()
        mock_workspace_client.subscriptions.return_value = mock_subscriptions

        mock_factory_instance = Mock()
        mock_factory_instance.create_workspaceevents_client.return_value = (
            mock_workspace_client
        )
        mock_factory_cls.return_value = mock_factory_instance

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
        mock_create.execute.assert_called_once()
        self.assertEqual(response, {"subscription_id": "test-subscription"})


if __name__ == "__main__":
    main()
