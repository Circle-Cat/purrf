import json
import unittest
from unittest.mock import MagicMock, patch
from google.pubsub_subscriber_store import pull_messages, renew_subscription


class FakeStreamingPullFuture:
    def result(self, timeout=None):
        raise TimeoutError("Fake timeout for testing.")

    def cancel(self):
        pass


class FakeSubscriber:
    def __init__(self):
        self.captured_callback = None

    def subscription_path(self, project_id, subscription_id):
        return f"projects/{project_id}/subscriptions/{subscription_id}"

    def subscribe(self, subscription_path, callback):
        self.captured_callback = callback
        return FakeStreamingPullFuture()


class TestPubsubSubscriberStore(unittest.TestCase):
    def setUp(self):
        self.fake_subscriber = FakeSubscriber()
        self.fake_client = MagicMock()
        self.fake_client.subscription_path.side_effect = self.fake_subscriber.subscription_path
        self.fake_client.subscribe.side_effect = self.fake_subscriber.subscribe

        patcher = patch("google.pubsub_subscriber_store.GoogleClientFactory")
        self.addCleanup(patcher.stop)
        self.mock_GoogleClientFactory = patcher.start()
        self.mock_GoogleClientFactory.return_value.create_subscriber_client.return_value = self.fake_client


    @patch("google.pubsub_subscriber_store.store_messages")
    @patch("google.pubsub_subscriber_store.get_ldap_by_id")
    def test_pull_chat_messages(self, mock_get_ldap_by_id, mock_store_messages):

        mock_get_ldap_by_id.return_value = "dummy_ldap"

        attribute_dict = {
            "ce-type": "google.workspace.chat.message.v1.created",
        }
        message_dict = {
            "message": {
                "name": "spaces/AAAAnmq4_MY/messages/TDV3Gvj7q0c.TDV3Gvj7q0c",
                "sender": {"name": "users/111457806489534158327", "type": "HUMAN"},
                "createTime": "2025-04-01T07:36:56.453983Z",
                "text": "123",
                "thread": {"name": "spaces/AAAAnmq4_MY/threads/TDV3Gvj7q0c"},
                "space": {"name": "spaces/AAAAnmq4_MY"},
                "argumentText": "123",
                "formattedText": "123",
            }
        }

        message_data = json.dumps(message_dict).encode("utf-8")
        fake_message = MagicMock()
        fake_message.get.side_effect = (
            lambda key, default=None: fake_message.__dict__.get(key, default)
        )
        fake_message.data = message_data
        fake_message.attributes = attribute_dict
        fake_message.publish_time.isoformat.return_value = "2025-04-01T07:36:56.453983Z"

        with self.assertRaises(TimeoutError):
            pull_messages("test_project", "test_subscription_id")

        self.fake_subscriber.captured_callback(fake_message)

        mock_store_messages.assert_called_once_with(
            "dummy_ldap",
            message_dict["message"],
            "created",
        )

        fake_message.ack.assert_called()

    @patch("google.pubsub_subscriber_store.renew_subscription")
    def test_pull_messages_expiration_reminder_success(self, mock_renew_subscription):
        message_dict = {
            "subscription": {"name": "subscriptions/test-id"}
        }
        attr = {
            "ce-type": "google.workspace.events.subscription.v1.expirationReminder"
        }

        msg = MagicMock()
        msg.data = json.dumps(message_dict).encode("utf-8")
        msg.attributes = attr

        with self.assertRaises(TimeoutError):
            pull_messages("test_project", "test_subscription")

        self.fake_subscriber.captured_callback(msg)
        mock_renew_subscription.assert_called_once_with("test_project", "subscriptions/test-id")
        msg.ack.assert_called_once()
    
    @patch("google.pubsub_subscriber_store.renew_subscription")
    def test_expiration_reminder_missing_subscription_name(self, mock_renew_subscription):
        message_dict = {"subscription": {}}
        attr = {
            "ce-type": "google.workspace.events.subscription.v1.expirationReminder"
        }

        msg = MagicMock()
        msg.data = json.dumps(message_dict).encode("utf-8")
        msg.attributes = attr

        with self.assertRaises(TimeoutError):
            pull_messages("test_project", "test_subscription")

        with self.assertRaises(ValueError):
            self.fake_subscriber.captured_callback(msg)
        msg.nack.assert_called_once()

    @patch("google.pubsub_subscriber_store.store_messages")
    @patch("google.pubsub_subscriber_store.get_ldap_by_id")
    def test_pull_messages_unknown_event_type(self, mock_get_ldap_by_id, mock_store):
        attr = {"ce-type": "unknown.event.type"}
        msg_dict = {"message": {"text": "hello"}}

        msg = MagicMock()
        msg.data = json.dumps(msg_dict).encode("utf-8")
        msg.attributes = attr

        with self.assertRaises(TimeoutError):
            pull_messages("test_project", "test_subscription")

        self.fake_subscriber.captured_callback(msg)
        mock_store.assert_not_called()
        msg.ack.assert_not_called()

    @patch("google.pubsub_subscriber_store.store_messages")
    @patch("google.pubsub_subscriber_store.get_ldap_by_id")
    def test_pull_messages_missing_fields(self, mock_get_ldap_by_id, mock_store):
        mock_get_ldap_by_id.return_value = "test_ldap"
        attr = {
            "ce-type": "google.workspace.chat.message.v1.created"
        }
        msg_dict = {
            "message": {
                "sender": {},
                "space": {"name": "spaces/test"}
            }
        }

        msg = MagicMock()
        msg.data = json.dumps(msg_dict).encode("utf-8")
        msg.attributes = attr

        with self.assertRaises(TimeoutError):
            pull_messages("test_project", "test_subscription")

        self.fake_subscriber.captured_callback(msg)
        mock_store.assert_called_once_with("", msg_dict["message"], "created")
        msg.ack.assert_called_once()


if __name__ == "__main__":
    unittest.main()
