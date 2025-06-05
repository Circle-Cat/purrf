from unittest import TestCase, main
from unittest.mock import Mock, patch
from src.historical_data.google_chat_history_fetcher import (
    list_directory_all_people_ldap,
)


class TestChatUtils(TestCase):
    @patch(
        "src.historical_data.google_chat_history_fetcher.GoogleClientFactory.create_people_client"
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
        "src.historical_data.google_chat_history_fetcher.GoogleClientFactory.create_people_client"
    )
    def test_list_directory_all_people_ldap_invalid_client(self, mock_client):
        mock_client.return_value = None
        with self.assertRaises(ValueError):
            list_directory_all_people_ldap()

    @patch(
        "src.historical_data.google_chat_history_fetcher.GoogleClientFactory.create_people_client"
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


if __name__ == "__main__":
    main()
