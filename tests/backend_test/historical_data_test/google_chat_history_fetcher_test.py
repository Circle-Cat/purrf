from unittest import TestCase, main
from unittest.mock import patch
from backend.historical_data.google_chat_history_fetcher import (
    list_directory_all_people_ldap,
    fetch_messages_by_spaces_id,
    fetch_history_messages,
)

TEST_SPACE_ID = "fhsdlfrp.dhiwqeq"
SPACE_ID_1 = "space1"
SPACE_ID_2 = "space2"
USER_ID_1 = "users/id1"
USER_ID_2 = "users/id2"
LDAP_1 = "ldap1"
LDAP_2 = "ldap2"
UNKNOWN_SENDER_ID = "unknown"
MESSAGE_TEXT_1 = "Hello"
MESSAGE_TEXT_2 = "Hi"
MOCK_MESSAGE_1 = {"sender": {"name": USER_ID_1}, "text": MESSAGE_TEXT_1}
MOCK_MESSAGE_2 = {"sender": {"name": USER_ID_2}, "text": MESSAGE_TEXT_2}
MOCK_MESSAGE_UNKNOWN = {"sender": {"name": "senderId/unknown"}, "text": MESSAGE_TEXT_1}
MOCK_SPACES = {SPACE_ID_1: "Space 1", SPACE_ID_2: "Space 2"}
MOCK_LDAP = {"id1": LDAP_1, "id2": LDAP_2}
MOCK_LDAP_PARTIAL = {"id1": LDAP_1}
MOCK_MESSAGES_RESPONSE = {
    "messages": [
        MOCK_MESSAGE_1,
        MOCK_MESSAGE_2,
    ],
    "nextPageToken": None,
}


class TestChatUtils(TestCase):
    @patch(
        "backend.historical_data.google_chat_history_fetcher.GoogleClientFactory.create_people_client"
    )
    def test_list_directory_all_people_ldap_success(self, mock_client):
        mock_people_response = {
            "people": [
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "id1"}},
                            "value": "user1@example.com",
                        }
                    ]
                },
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "id2"}},
                            "value": "user2@example.com",
                        }
                    ]
                },
            ],
            "nextPageToken": None,
        }
        mock_client.return_value.people.return_value.listDirectoryPeople.return_value.execute.return_value = mock_people_response
        result = list_directory_all_people_ldap()
        expected_result = {"id1": "user1", "id2": "user2"}
        self.assertEqual(result, expected_result)
        mock_client.return_value.people.return_value.listDirectoryPeople.assert_called_once_with(
            readMask="emailAddresses",
            pageSize=100,
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageToken=None,
        )

    @patch(
        "backend.historical_data.google_chat_history_fetcher.GoogleClientFactory.create_people_client"
    )
    def test_list_directory_all_people_ldap_invalid_client(self, mock_client):
        mock_client.return_value = None
        with self.assertRaises(ValueError):
            list_directory_all_people_ldap()

    @patch(
        "backend.historical_data.google_chat_history_fetcher.GoogleClientFactory.create_people_client"
    )
    def test_list_directory_all_people_ldap_empty_result_raises_error(
        self, mock_client
    ):
        """
        Test that list_directory_all_people_ldap raises ValueError
        if no directory people are returned.
        """
        mock_execute = mock_client.return_value.people.return_value.listDirectoryPeople.return_value.execute
        mock_execute.return_value = {"people": [], "nextPageToken": None}
        with self.assertRaises(ValueError):
            list_directory_all_people_ldap()

    @patch(
        "backend.historical_data.google_chat_history_fetcher.GoogleClientFactory.create_chat_client"
    )
    def test_fetch_messages_by_spaces_id_success(self, mock_client):
        mock_client.return_value.spaces.return_value.messages.return_value.list.return_value.execute.return_value = MOCK_MESSAGES_RESPONSE
        result = fetch_messages_by_spaces_id(TEST_SPACE_ID)
        expected_result = MOCK_MESSAGES_RESPONSE["messages"]
        self.assertEqual(result, expected_result)
        mock_client.return_value.spaces.return_value.messages.return_value.list.assert_called_once_with(
            parent=f"spaces/{TEST_SPACE_ID}", pageSize=100, pageToken=None
        )

    @patch(
        "backend.historical_data.google_chat_history_fetcher.GoogleClientFactory.create_chat_client"
    )
    def test_fetch_messages_by_spaces_id_invalid_client(self, mock_client):
        mock_client.return_value = None
        with self.assertRaises(ValueError):
            fetch_messages_by_spaces_id(TEST_SPACE_ID)

    @patch("backend.historical_data.google_chat_history_fetcher.store_messages")
    @patch(
        "backend.historical_data.google_chat_history_fetcher.list_directory_all_people_ldap"
    )
    @patch(
        "backend.historical_data.google_chat_history_fetcher.fetch_messages_by_spaces_id"
    )
    @patch("backend.historical_data.google_chat_history_fetcher.get_chat_spaces")
    def test_fetch_history_messages_success(
        self,
        mock_get_spaces,
        mock_fetch_messages,
        mock_list_ldap,
        mock_store_messages,
    ):
        mock_get_spaces.return_value = MOCK_SPACES
        mock_fetch_messages.side_effect = [[MOCK_MESSAGE_1], [MOCK_MESSAGE_2]]
        mock_list_ldap.return_value = MOCK_LDAP
        mock_store_messages.return_value = None
        fetch_history_messages()
        mock_get_spaces.assert_called_once()
        mock_fetch_messages.assert_any_call(SPACE_ID_1)
        mock_fetch_messages.assert_any_call(SPACE_ID_2)
        self.assertEqual(mock_fetch_messages.call_count, 2)
        mock_list_ldap.assert_called_once()
        self.assertEqual(mock_store_messages.call_count, 2)

    @patch("backend.historical_data.google_chat_history_fetcher.store_messages")
    @patch(
        "backend.historical_data.google_chat_history_fetcher.list_directory_all_people_ldap"
    )
    @patch(
        "backend.historical_data.google_chat_history_fetcher.fetch_messages_by_spaces_id"
    )
    @patch("backend.historical_data.google_chat_history_fetcher.get_chat_spaces")
    def test_fetch_history_messages_with_unknown_sender(
        self,
        mock_get_spaces,
        mock_fetch_messages,
        mock_list_ldap,
        mock_store_messages,
    ):
        mock_get_spaces.return_value = MOCK_SPACES
        mock_fetch_messages.side_effect = [
            [MOCK_MESSAGE_UNKNOWN],
            [MOCK_MESSAGE_UNKNOWN],
        ]
        mock_list_ldap.return_value = MOCK_LDAP_PARTIAL
        mock_store_messages.return_value = None
        fetch_history_messages()
        mock_get_spaces.assert_called_once()
        mock_fetch_messages.assert_any_call(SPACE_ID_1)
        mock_fetch_messages.assert_any_call(SPACE_ID_2)
        self.assertEqual(mock_fetch_messages.call_count, 2)
        mock_list_ldap.assert_called_once()
        mock_store_messages.assert_not_called()


if __name__ == "__main__":
    main()
