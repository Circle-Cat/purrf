import json
from unittest import TestCase, main
from unittest.mock import MagicMock

from backend.consumers.google_chat_processor_service import GoogleChatProcessorService
from backend.common.constants import (
    EXPIRATION_REMINDER_EVENT,
    EVENT_TYPES,
)


class FakeMessage:
    def __init__(self, data, attributes):
        if isinstance(data, dict):
            self.data = json.dumps(data).encode("utf-8")
        else:
            self.data = data.encode("utf-8")
        self.attributes = attributes
        self.ack = MagicMock()
        self.nack = MagicMock()
        self.message_id = "fake-message-id"


class TestGoogleChatProcessorService(TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.pubsub_puller_factory = MagicMock()
        self.google_chat_messages_utils = MagicMock()
        self.google_service = MagicMock()

        self.service = GoogleChatProcessorService(
            logger=self.logger,
            pubsub_puller_factory=self.pubsub_puller_factory,
            google_chat_messages_utils=self.google_chat_messages_utils,
            google_service=self.google_service,
        )
        self.project_id = "test-project"
        self.subscription_id = "test-subscription"

    def test_pull_messages_success(self):
        """Test that pull_messages correctly initializes and starts the puller."""
        mock_puller = MagicMock()
        self.pubsub_puller_factory.get_puller_instance.return_value = mock_puller

        self.service.pull_messages(self.project_id, self.subscription_id)

        self.pubsub_puller_factory.get_puller_instance.assert_called_once_with(
            self.project_id, self.subscription_id
        )
        mock_puller.start_pulling_messages.assert_called_once_with(
            self.service.callback
        )

    def test_pull_messages_missing_project_id(self):
        """Test that pull_messages raises ValueError for a missing project_id."""
        with self.assertRaises(ValueError):
            self.service.pull_messages(
                project_id=None, subscription_id=self.subscription_id
            )

    def test_pull_messages_missing_subscription_id(self):
        """Test that pull_messages raises ValueError for a missing subscription_id."""
        with self.assertRaises(ValueError):
            self.service.pull_messages(project_id=self.project_id, subscription_id="")

    def test_callback_expiration_reminder_success(self):
        """Test callback handling of a subscription expiration reminder event."""
        subscription_name = "subscriptions/test-sub"
        message = FakeMessage(
            data={"subscription": {"name": subscription_name}},
            attributes={"ce-type": EXPIRATION_REMINDER_EVENT},
        )

        self.service.callback(message)

        self.google_service.renew_subscription.assert_called_once_with(
            subscription_name
        )
        message.ack.assert_called_once()
        message.nack.assert_not_called()

    def test_callback_expiration_reminder_no_name(self):
        """Test callback handling of an expiration reminder with no subscription name."""
        message = FakeMessage(
            data={"subscription": {}},
            attributes={"ce-type": EXPIRATION_REMINDER_EVENT},
        )

        with self.assertRaises(ValueError):
            self.service.callback(message)

        self.google_service.renew_subscription.assert_not_called()
        message.ack.assert_not_called()
        message.nack.assert_called_once()

    def test_callback_chat_message_created(self):
        """Test callback handling of a chat message creation event."""
        sender_id = "12345"
        sender_ldap = "test.user"
        chat_message = {
            "sender": {"name": f"users/{sender_id}"},
            "text": "hello",
        }
        message_type = "google.workspace.chat.message.v1.created"
        self.assertIn(message_type, EVENT_TYPES)

        message = FakeMessage(
            data={"message": chat_message},
            attributes={"ce-type": message_type},
        )
        self.google_service.get_ldap_by_id.return_value = sender_ldap

        self.service.callback(message)

        self.google_service.get_ldap_by_id.assert_called_once_with(sender_id)
        self.google_chat_messages_utils.store_messages.assert_called_once_with(
            sender_ldap, chat_message, "created"
        )
        message.ack.assert_called_once()
        message.nack.assert_not_called()

    def test_callback_chat_message_no_sender_id(self):
        """Test callback handling of a chat message with no sender ID."""
        chat_message = {
            "sender": {"name": "users/"},
            "text": "hello",
        }
        message_type = "google.workspace.chat.message.v1.created"
        self.assertIn(message_type, EVENT_TYPES)

        message = FakeMessage(
            data={"message": chat_message},
            attributes={"ce-type": message_type},
        )

        self.service.callback(message)

        self.google_service.get_ldap_by_id.assert_not_called()
        self.google_chat_messages_utils.store_messages.assert_called_once_with(
            "", chat_message, "created"
        )
        message.ack.assert_called_once()
        message.nack.assert_not_called()

    def test_callback_unsupported_event_type(self):
        """Test that unsupported event types are ignored."""
        message = FakeMessage(
            data={"message": {}},
            attributes={"ce-type": "unsupported.event.type"},
        )

        self.service.callback(message)

        self.google_service.get_ldap_by_id.assert_not_called()
        self.google_chat_messages_utils.store_messages.assert_not_called()
        message.ack.assert_not_called()
        message.nack.assert_not_called()

    def test_callback_invalid_json_data(self):
        """Test callback handling of a message with invalid JSON data."""
        message = FakeMessage(
            data="this is not json",
            attributes={"ce-type": "google.workspace.chat.message.v1.created"},
        )

        self.service.callback(message)

        self.google_service.get_ldap_by_id.assert_not_called()
        self.google_chat_messages_utils.store_messages.assert_not_called()
        message.ack.assert_not_called()
        message.nack.assert_called_once()


if __name__ == "__main__":
    main()
