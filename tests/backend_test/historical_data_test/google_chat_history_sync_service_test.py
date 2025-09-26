from unittest import TestCase, main
from unittest.mock import Mock, call

from backend.historical_data.google_chat_history_sync_service import (
    GoogleChatHistorySyncService,
)


class TestGoogleChatHistorySyncService(TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_logger = Mock()
        self.mock_google_service = Mock()
        self.mock_google_chat_message_utils = Mock()

        self.service = GoogleChatHistorySyncService(
            self.mock_logger,
            self.mock_google_service,
            self.mock_google_chat_message_utils,
        )

    def test_sync_history_messages_happy_path(self):
        """
        Test the happy path where spaces and messages are found and processed.
        """

        spaces = {"space/1": "Space One", "space/2": "Space Two"}
        ldaps = {"user/123": "ldap1"}
        messages_batch_1 = [{"name": "msg1"}, {"name": "msg2"}]
        messages_batch_2 = [{"name": "msg3"}]

        self.mock_google_service.get_chat_spaces.return_value = spaces
        self.mock_google_service.list_directory_all_people_ldap.return_value = ldaps
        self.mock_google_service.fetch_messages_by_spaces_id_paginated.side_effect = [
            iter([messages_batch_1]),  # Messages for space/1
            iter([messages_batch_2]),  # Messages for space/2
        ]

        self.service.sync_history_messages()

        self.mock_google_service.get_chat_spaces.assert_called_once_with("SPACE")
        self.mock_google_service.list_directory_all_people_ldap.assert_called_once()
        self.mock_google_service.fetch_messages_by_spaces_id_paginated.assert_has_calls(
            [call("space/1"), call("space/2")], any_order=True
        )
        self.mock_google_chat_message_utils.sync_batch_created_messages.assert_has_calls(
            [
                call(messages_batch_1, ldaps),
                call(messages_batch_2, ldaps),
            ],
            any_order=True,
        )
        self.assertEqual(
            self.mock_google_chat_message_utils.sync_batch_created_messages.call_count,
            2,
        )

    def test_sync_history_messages_no_messages_in_space(self):
        """
        Test behavior for a space that contains no messages.
        """

        spaces = {"space/1": "Space One"}
        self.mock_google_service.get_chat_spaces.return_value = spaces
        self.mock_google_service.list_directory_all_people_ldap.return_value = {
            "user/1": "ldap1"
        }
        self.mock_google_service.fetch_messages_by_spaces_id_paginated.return_value = (
            iter([[]])
        )

        self.service.sync_history_messages()

        self.mock_google_service.fetch_messages_by_spaces_id_paginated.assert_called_once_with(
            "space/1"
        )
        self.mock_google_chat_message_utils.sync_batch_created_messages.assert_not_called()

    def test_sync_history_messages_exception_handling(self):
        """
        Test that exceptions during the process are caught, and re-raised.
        """

        error_message = "Service unavailable"
        self.mock_google_service.get_chat_spaces.side_effect = Exception(error_message)

        with self.assertRaises(Exception) as context:
            self.service.sync_history_messages()

        self.assertTrue(error_message in str(context.exception))

    def test_sync_history_messages_no_spaces_found(self):
        """
        Test that exceptions when no Google Chat spaces are found.
        """

        self.mock_google_service.get_chat_spaces.return_value = {}

        with self.assertRaises(ValueError):
            self.service.sync_history_messages()

        self.mock_google_service.get_chat_spaces.assert_called_once_with("SPACE")
        self.mock_google_service.list_directory_all_people_ldap.assert_not_called()
        self.mock_google_service.fetch_messages_by_spaces_id_paginated.assert_not_called()

    def test_sync_history_messages_no_ldap_mappings(self):
        """
        Test that exceptions when no LDAP mappings are found.
        """

        spaces = {"space/1": "Space One"}
        self.mock_google_service.get_chat_spaces.return_value = spaces
        self.mock_google_service.list_directory_all_people_ldap.return_value = {}

        with self.assertRaises(ValueError):
            self.service.sync_history_messages()

        self.mock_google_service.list_directory_all_people_ldap.assert_called_once()
        self.mock_google_service.fetch_messages_by_spaces_id_paginated.assert_not_called()


if __name__ == "__main__":
    main()
