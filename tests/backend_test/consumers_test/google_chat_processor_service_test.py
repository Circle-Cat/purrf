import json
from unittest import TestCase, main
from unittest.mock import MagicMock

from backend.consumers.google_chat_processor_service import GoogleChatProcessorService
from backend.common.constants import (
    EXPIRATION_REMINDER_EVENT,
    SINGLE_GOOGLE_CHAT_EVENT_TYPES,
    ALL_GOOGLE_CHAT_EVENT_TYPES,
    GoogleChatEventType,
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
        sender_name_full = f"users/{sender_id}"
        sender_ldap = "test.user"
        chat_message_payload = {
            "message": {
                "sender": {"name": sender_name_full},
                "text": "hello",
            }
        }
        message_type_full = "google.workspace.chat.message.v1.created"
        self.assertIn(message_type_full, SINGLE_GOOGLE_CHAT_EVENT_TYPES)

        message = FakeMessage(
            data=chat_message_payload,
            attributes={"ce-type": message_type_full},
        )
        self.google_service.get_ldap_by_id.return_value = sender_ldap

        self.service.callback(message)

        self.google_service.get_ldap_by_id.assert_called_once_with(sender_id)
        self.google_chat_messages_utils.store_messages.assert_called_once_with(
            {sender_name_full: sender_ldap},  # ldaps_dict
            [chat_message_payload],  # messages_list
            GoogleChatEventType.CREATED,  # message_enum
        )
        message.ack.assert_called_once()
        message.nack.assert_not_called()

    def test_callback_chat_message_no_sender_id(self):
        """Test callback handling of a chat message with no sender ID."""
        sender_name_full = "users/"
        chat_message_payload = {
            "message": {
                "sender": {"name": sender_name_full},
                "text": "hello",
            }
        }
        message_type_full = "google.workspace.chat.message.v1.created"
        self.assertIn(message_type_full, SINGLE_GOOGLE_CHAT_EVENT_TYPES)

        message = FakeMessage(
            data=chat_message_payload,
            attributes={"ce-type": message_type_full},
        )

        self.service.callback(message)

        self.google_service.get_ldap_by_id.assert_not_called()
        self.google_chat_messages_utils.store_messages.assert_called_once_with(
            {sender_name_full: ""},  # ldaps_dict
            [chat_message_payload],  # messages_list
            GoogleChatEventType.CREATED,  # message_enum
        )
        message.ack.assert_called_once()
        message.nack.assert_not_called()

    def test_callback_batch_chat_message_created(self):
        """Test callback handling of a batch chat message creation event."""
        all_people_ldap = {"user/1": "user1.ldap", "user/2": "user2.ldap"}
        batch_messages_payload = {
            "messages": [
                {"message": {"sender": {"name": "user/1"}, "text": "batch_hello_1"}},
                {"message": {"sender": {"name": "user/2"}, "text": "batch_hello_2"}},
            ]
        }
        message_type_full = "google.workspace.chat.message.v1.batchCreated"
        self.assertNotIn(message_type_full, SINGLE_GOOGLE_CHAT_EVENT_TYPES)
        self.assertIn(message_type_full, ALL_GOOGLE_CHAT_EVENT_TYPES)

        message = FakeMessage(
            data=batch_messages_payload,
            attributes={"ce-type": message_type_full},
        )
        self.google_service.list_directory_all_people_ldap.return_value = (
            all_people_ldap
        )

        self.service.callback(message)

        self.google_service.list_directory_all_people_ldap.assert_called_once()
        self.google_chat_messages_utils.store_messages.assert_called_once_with(
            all_people_ldap,  # ldaps_dict
            batch_messages_payload.get("messages"),  # messages_list
            GoogleChatEventType.BATCH_CREATED,  # message_enum
        )
        message.ack.assert_called_once()
        message.nack.assert_not_called()

    def test_callback_unsupported_event_type(self):
        """Test that unsupported event types are NACKed."""
        message = FakeMessage(
            data={"message": {}},
            attributes={"ce-type": "unsupported.event.type"},
        )

        self.service.callback(message)

        self.google_service.get_ldap_by_id.assert_not_called()
        self.google_chat_messages_utils.store_messages.assert_not_called()
        message.ack.assert_not_called()
        message.nack.assert_called_once()

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
