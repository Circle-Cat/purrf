from unittest import TestCase, main
from unittest.mock import Mock, patch, MagicMock
from src.consumers.google_chat_consumer import (
    get_ldap_by_id,
    pull_messages,
    EXPIRATION_REMINDER_EVENT,
    renew_subscription,
)
import json


class TestChatUtils(TestCase):
    @patch(
        "src.consumers.google_chat_consumer.GoogleClientFactory.create_people_client"
    )
    def test_get_ldap_by_id_success(self, mock_client):
        mock_people_service = mock_client.return_value
        mock_get = mock_people_service.people.return_value.get.return_value.execute

        mock_get.return_value = {"emailAddresses": [{"value": "test.user@example.com"}]}

        result = get_ldap_by_id("12345")
        self.assertEqual(result, "test.user")

        mock_people_service.people.return_value.get.assert_called_once_with(
            resourceName="people/12345", personFields="emailAddresses"
        )

    @patch(
        "src.consumers.google_chat_consumer.GoogleClientFactory.create_people_client"
    )
    def test_get_ldap_by_id_no_email(self, mock_client):
        mock_people_service = mock_client.return_value
        mock_get = mock_people_service.people.return_value.get.return_value.execute

        mock_get.return_value = {"emailAddresses": []}

        result = get_ldap_by_id("12345")
        self.assertIsNone(result)

    @patch(
        "src.consumers.google_chat_consumer.GoogleClientFactory.create_people_client"
    )
    def test_get_ldap_by_id_retry_success(self, mock_client):
        mock_people_service = mock_client.return_value
        mock_get = mock_people_service.people.return_value.get.return_value.execute

        mock_get.side_effect = [
            Exception("Temporary error"),
            {"emailAddresses": [{"value": "user@example.com"}]},
        ]

        result = get_ldap_by_id("12345")

        self.assertEqual(result, "user")
        self.assertEqual(mock_get.call_count, 2)


class FakeMessage:
    def __init__(self, payload: dict, attributes: dict):
        self.data = json.dumps(payload).encode("utf-8")
        self.attributes = attributes
        self.ack = MagicMock()
        self.nack = MagicMock()
        self.message_id = "fake-msg-id"


class TestPullMessages(TestCase):
    def setUp(self):
        self.project_id = "proj"
        self.subscription_id = "sub"

    @patch("src.consumers.google_chat_consumer.PubSubPuller")
    def test_puller_instantiation(self, mock_puller_cls):
        fake_puller = MagicMock()
        mock_puller_cls.return_value = fake_puller

        pull_messages(self.project_id, self.subscription_id)

        mock_puller_cls.assert_called_once_with(self.project_id, self.subscription_id)
        fake_puller.start_pulling_messages.assert_called_once()
        cb = fake_puller.start_pulling_messages.call_args[0][0]
        self.assertTrue(callable(cb))

    @patch("src.consumers.google_chat_consumer.PubSubPuller")
    @patch("src.consumers.google_chat_consumer.renew_subscription")
    def test_expiration_reminder(self, mock_renew, mock_puller_cls):
        fake_puller = MagicMock()
        mock_puller_cls.return_value = fake_puller
        pull_messages(self.project_id, self.subscription_id)
        cb = fake_puller.start_pulling_messages.call_args[0][0]

        msg = FakeMessage(
            {"subscription": {"name": "subscriptions/42"}},
            {"ce-type": EXPIRATION_REMINDER_EVENT},
        )
        cb(msg)

        mock_renew.assert_called_once_with(self.project_id, "subscriptions/42")
        msg.ack.assert_called_once()
        msg.nack.assert_not_called()

    @patch("src.consumers.google_chat_consumer.PubSubPuller")
    @patch("src.consumers.google_chat_consumer.renew_subscription")
    def test_expiration_reminder_missing_name(self, mock_renew, mock_puller_cls):
        fake_puller = MagicMock()
        mock_puller_cls.return_value = fake_puller
        pull_messages(self.project_id, self.subscription_id)
        cb = fake_puller.start_pulling_messages.call_args[0][0]

        msg = FakeMessage({"subscription": {}}, {"ce-type": EXPIRATION_REMINDER_EVENT})

        with self.assertRaises(ValueError):
            cb(msg)

        msg.nack.assert_called_once()
        mock_renew.assert_not_called()

    @patch("src.consumers.google_chat_consumer.GoogleClientFactory")
    def test_renew_subscription_calls_patch_and_execute(self, mock_client):
        fake_service = MagicMock()
        mock_client.return_value.create_workspaceevents_client.return_value = (
            fake_service
        )

        fake_patch_op = MagicMock()
        fake_patch_op.execute.return_value = {"status": "ok"}
        fake_service.subscriptions.return_value.patch.return_value = fake_patch_op

        project_id = "proj-123"
        subscription_name = "subscriptions/my-sub"

        renew_subscription(project_id, subscription_name)

        fake_service.subscriptions.assert_called_once_with()

        fake_service.subscriptions.return_value.patch.assert_called_once_with(
            name=subscription_name,
            updateMask="ttl",
            body={"ttl": {"seconds": 0}},
        )

        fake_patch_op.execute.assert_called_once()

    @patch("src.consumers.google_chat_consumer.GoogleClientFactory")
    def test_renew_subscription_propagates_errors(self, mock_gcf):
        fake_service = MagicMock()
        mock_gcf.return_value.create_workspaceevents_client.return_value = fake_service

        fake_patch_op = MagicMock()
        fake_patch_op.execute.side_effect = RuntimeError("API error")
        fake_service.subscriptions.return_value.patch.return_value = fake_patch_op

        with self.assertRaises(RuntimeError) as cm:
            renew_subscription("proj-123", "subscriptions/my-sub")
        self.assertIn("API error", str(cm.exception))

    @patch("src.consumers.google_chat_consumer.store_messages")
    @patch("src.consumers.google_chat_consumer.get_ldap_by_id")
    @patch("src.consumers.google_chat_consumer.PubSubPuller")
    def test_pull_chat_messages(self, mock_puller_cls, mock_get_ldap_by_id, mock_store):
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

        pull_messages("proj", "sub")

        mock_puller_cls.assert_called_once_with(self.project_id, self.subscription_id)
        cb = mock_puller_cls.return_value.start_pulling_messages.call_args[0][0]

        cb(fake_message)
        mock_store.assert_called_once_with(
            "dummy_ldap",
            message_dict["message"],
            "created",
        )

        fake_message.ack.assert_called_once()
        fake_message.nack.assert_not_called()

    @patch("src.consumers.google_chat_consumer.store_messages")
    @patch("src.consumers.google_chat_consumer.get_ldap_by_id")
    @patch("src.consumers.google_chat_consumer.PubSubPuller")
    def test_pull_messages_unknown_event_type(
        self, mock_puller_cls, mock_get_ldap, mock_store
    ):
        fake_puller = MagicMock()
        mock_puller_cls.return_value = fake_puller

        pull_messages("test_project", "test_subscription")

        mock_puller_cls.assert_called_once_with("test_project", "test_subscription")

        cb = fake_puller.start_pulling_messages.call_args[0][0]
        self.assertTrue(callable(cb))

        msg = MagicMock()
        msg.data = json.dumps({"message": {"text": "hello"}}).encode("utf-8")
        msg.attributes = {"ce-type": "unknown.event.type"}

        cb(msg)

        mock_store.assert_not_called()
        msg.ack.assert_not_called()
        msg.nack.assert_not_called()

    @patch("src.consumers.google_chat_consumer.store_messages")
    @patch("src.consumers.google_chat_consumer.get_ldap_by_id")
    @patch("src.consumers.google_chat_consumer.PubSubPuller")
    def test_pull_messages_missing_fields(
        self, mock_puller_cls, mock_get_ldap, mock_store
    ):
        fake_puller = MagicMock()
        mock_puller_cls.return_value = fake_puller
        mock_get_ldap.return_value = "test_ldap"

        pull_messages("test_project", "test_subscription")

        mock_puller_cls.assert_called_once_with("test_project", "test_subscription")

        cb = fake_puller.start_pulling_messages.call_args[0][0]

        msg = MagicMock()
        msg.data = json.dumps({
            "message": {"sender": {}, "space": {"name": "spaces/test"}}
        }).encode("utf-8")
        msg.attributes = {"ce-type": "google.workspace.chat.message.v1.created"}

        cb(msg)

        mock_store.assert_called_once_with(
            "",
            {"sender": {}, "space": {"name": "spaces/test"}},
            "created",
        )
        msg.ack.assert_called_once()
        msg.nack.assert_not_called()


if __name__ == "__main__":
    main()
