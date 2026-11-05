from unittest import TestCase, main
from unittest.mock import MagicMock

from backend.consumers.google_chat_processor_service import GoogleChatProcessorService
from backend.common.constants import (
    EXPIRATION_REMINDER_EVENT,
    SINGLE_GOOGLE_CHAT_EVENT_TYPES,
    ALL_GOOGLE_CHAT_EVENT_TYPES,
    GoogleChatEventType,
)


class TestGoogleChatProcessorService(TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.google_chat_messages_utils = MagicMock()
        self.google_service = MagicMock()

        self.service = GoogleChatProcessorService(
            logger=self.logger,
            google_chat_messages_utils=self.google_chat_messages_utils,
            google_service=self.google_service,
        )

    def test_process_event_expiration_reminder_success(self):
        """Test handling of a subscription expiration reminder event."""
        subscription_name = "subscriptions/test-sub"

        self.service.process_event(
            {"subscription": {"name": subscription_name}},
            {"ce-type": EXPIRATION_REMINDER_EVENT},
        )

        self.google_service.renew_subscription.assert_called_once_with(
            subscription_name
        )

    def test_process_event_expiration_reminder_no_name(self):
        """Test that an expiration reminder with no subscription name raises."""
        with self.assertRaises(ValueError):
            self.service.process_event(
                {"subscription": {}},
                {"ce-type": EXPIRATION_REMINDER_EVENT},
            )

        self.google_service.renew_subscription.assert_not_called()

    def test_process_event_chat_message_created(self):
        """Test handling of a chat message creation event."""
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
        self.google_service.get_ldap_by_id.return_value = sender_ldap

        self.service.process_event(chat_message_payload, {"ce-type": message_type_full})

        self.google_service.get_ldap_by_id.assert_called_once_with(sender_id)
        self.google_chat_messages_utils.store_messages.assert_called_once_with(
            {sender_name_full: sender_ldap},  # ldaps_dict
            [chat_message_payload],  # messages_list
            GoogleChatEventType.CREATED,  # message_enum
        )

    def test_process_event_chat_message_no_sender_id(self):
        """Test handling of a chat message with no sender ID."""
        sender_name_full = "users/"
        chat_message_payload = {
            "message": {
                "sender": {"name": sender_name_full},
                "text": "hello",
            }
        }
        message_type_full = "google.workspace.chat.message.v1.created"
        self.assertIn(message_type_full, SINGLE_GOOGLE_CHAT_EVENT_TYPES)

        self.service.process_event(chat_message_payload, {"ce-type": message_type_full})

        self.google_service.get_ldap_by_id.assert_not_called()
        self.google_chat_messages_utils.store_messages.assert_called_once_with(
            {sender_name_full: ""},  # ldaps_dict
            [chat_message_payload],  # messages_list
            GoogleChatEventType.CREATED,  # message_enum
        )

    def test_process_event_batch_chat_message_created(self):
        """Test handling of a batch chat message creation event."""
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
        self.google_service.list_directory_all_people_ldap.return_value = (
            all_people_ldap
        )

        self.service.process_event(
            batch_messages_payload, {"ce-type": message_type_full}
        )

        self.google_service.list_directory_all_people_ldap.assert_called_once()
        self.google_chat_messages_utils.store_messages.assert_called_once_with(
            all_people_ldap,  # ldaps_dict
            batch_messages_payload.get("messages"),  # messages_list
            GoogleChatEventType.BATCH_CREATED,  # message_enum
        )

    def test_process_event_unsupported_event_type(self):
        """Test that unsupported event types raise ValueError."""
        with self.assertRaises(ValueError):
            self.service.process_event(
                {"message": {}}, {"ce-type": "unsupported.event.type"}
            )

        self.google_service.get_ldap_by_id.assert_not_called()
        self.google_chat_messages_utils.store_messages.assert_not_called()


if __name__ == "__main__":
    main()
