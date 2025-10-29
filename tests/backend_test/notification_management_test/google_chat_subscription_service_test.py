from unittest import TestCase, main
from unittest.mock import MagicMock
from backend.notification_management.google_chat_subscription_service import (
    GoogleChatSubscriptionService,
)

TEST_PROJECT_ID = "test-project"
TEST_TOPIC_ID = "test-topic"
TEST_SPACE_ID = "test-space"
TEST_EVENT_TYPES = ["google.workspace.chat.message.v1.created"]


class TestGoogleChatSubscriptionService(TestCase):
    def setUp(self):
        self.mock_workspace_client = MagicMock()
        self.mock_subscriptions = MagicMock()
        self.mock_create = MagicMock()
        self.mock_subscriptions.create.return_value = self.mock_create
        self.mock_workspace_client.subscriptions.return_value = self.mock_subscriptions

        self.mock_logger = MagicMock()

        self.mock_retry_utils = MagicMock()
        self.mock_retry_utils.get_retry_on_transient = MagicMock()
        self.svc = GoogleChatSubscriptionService(
            logger=self.mock_logger,
            google_workspaceevents_client=self.mock_workspace_client,
            retry_utils=self.mock_retry_utils,
        )

    def test_create_workspaces_subscriptions_success_first_try(self):
        expected_response = {"subscription_id": "test-subscription"}
        self.mock_retry_utils.get_retry_on_transient.return_value = expected_response

        resp = self.svc.create_workspaces_subscriptions(
            project_id=TEST_PROJECT_ID,
            topic_id=TEST_TOPIC_ID,
            space_id=TEST_SPACE_ID,
            event_types=TEST_EVENT_TYPES,
        )

        expected_body = {
            "target_resource": f"//chat.googleapis.com/spaces/{TEST_SPACE_ID}",
            "event_types": TEST_EVENT_TYPES,
            "notification_endpoint": {
                "pubsub_topic": f"projects/{TEST_PROJECT_ID}/topics/{TEST_TOPIC_ID}"
            },
            "payload_options": {"include_resource": True},
        }
        self.mock_subscriptions.create.assert_called_once_with(body=expected_body)

        subscription = self.mock_subscriptions.create.return_value
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            subscription.execute
        )
        self.assertEqual(resp, expected_response)

    def test_create_workspaces_subscriptions_retries_then_succeeds(self):
        self.mock_create.execute.side_effect = [
            RuntimeError("transient"),
            {"subscription_id": "retry-success"},
        ]

        def fake_retry_call(fn, *args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except RuntimeError:
                return fn(*args, **kwargs)

        self.mock_retry_utils.get_retry_on_transient.side_effect = fake_retry_call

        resp = self.svc.create_workspaces_subscriptions(
            project_id=TEST_PROJECT_ID,
            topic_id=TEST_TOPIC_ID,
            space_id=TEST_SPACE_ID,
            event_types=TEST_EVENT_TYPES,
        )

        self.assertEqual(self.mock_create.execute.call_count, 2)
        self.assertEqual(resp, {"subscription_id": "retry-success"})

        subscription = self.mock_subscriptions.create.return_value
        self.mock_retry_utils.get_retry_on_transient.assert_called_with(
            subscription.execute
        )

    def test_create_workspaces_subscriptions_rejects_empty_event_types(self):
        with self.assertRaises(ValueError):
            self.svc.create_workspaces_subscriptions(
                project_id=TEST_PROJECT_ID,
                topic_id=TEST_TOPIC_ID,
                space_id=TEST_SPACE_ID,
                event_types=[],  # invalid
            )
        self.mock_retry_utils.get_retry_on_transient.assert_not_called()


if __name__ == "__main__":
    main()
