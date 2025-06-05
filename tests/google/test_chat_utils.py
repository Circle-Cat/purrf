from unittest import TestCase, main
from unittest.mock import Mock, patch
import logging
from io import StringIO
from google.chat_utils import (
    list_directory_all_people_ldap,
    get_ldap_by_id,
)
from google.constants import (
    CHAT_API_NAME,
    NO_CLIENT_ERROR_MSG,
    DEFAULT_PAGE_SIZE,
    DEFAULT_SPACE_TYPE,
    RETRIEVED_PEOPLE_INFO_MSG,
    PEOPLE_API_NAME,
)

space_type = DEFAULT_SPACE_TYPE


class TestChatUtils(TestCase):
    @patch("google.authentication_utils.GoogleClientFactory.create_people_client")
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
            pageSize=DEFAULT_PAGE_SIZE,
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageToken=None,
        )

    @patch("google.authentication_utils.GoogleClientFactory.create_people_client")
    def test_list_directory_all_people_ldap_invalid_client(self, mock_client):
        mock_client.return_value = None

        with self.assertRaises(ValueError) as context:
            list_directory_all_people_ldap()
        self.assertEqual(
            str(context.exception),
            NO_CLIENT_ERROR_MSG.format(client_name=PEOPLE_API_NAME),
        )

    @patch("google.authentication_utils.GoogleClientFactory.create_people_client")
    def test_list_directory_all_people_ldap_empty_result_raises_error(
        self, mock_client
    ):
        """
        Test that list_directory_all_people_ldap raises ValueError
        if no directory people are returned.
        """
        mock_execute = mock_client.return_value.people.return_value.listDirectoryPeople.return_value.execute
        mock_execute.return_value = {"people": [], "nextPageToken": None}

        with self.assertRaises(ValueError) as context:
            list_directory_all_people_ldap()
        self.assertIn("No directory people were found", str(context.exception))

    @patch("google.authentication_utils.GoogleClientFactory.create_people_client")
    def test_get_ldap_by_id_success(self, mock_client):
        mock_people_service = mock_client.return_value
        mock_get = mock_people_service.people.return_value.get.return_value.execute

        mock_get.return_value = {"emailAddresses": [{"value": "test.user@example.com"}]}

        result = get_ldap_by_id("12345")
        self.assertEqual(result, "test.user")

        mock_people_service.people.return_value.get.assert_called_once_with(
            resourceName="people/12345", personFields="emailAddresses"
        )

    @patch("google.authentication_utils.GoogleClientFactory.create_people_client")
    def test_get_ldap_by_id_no_email(self, mock_client):
        mock_people_service = mock_client.return_value
        mock_get = mock_people_service.people.return_value.get.return_value.execute

        mock_get.return_value = {"emailAddresses": []}

        result = get_ldap_by_id("12345")
        self.assertIsNone(result)

    @patch("google.authentication_utils.GoogleClientFactory.create_people_client")
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


if __name__ == "__main__":
    main()
