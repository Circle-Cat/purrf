from unittest import TestCase, main
from unittest.mock import Mock, patch
import logging
from io import StringIO
from google.chat_utils import get_chat_spaces, list_directory_all_people_ldap
from google.constants import (
    CHAT_API_NAME,
    NO_CLIENT_ERROR_MSG,
    RETRIEVED_SPACES_INFO_MSG,
    DEFAULT_PAGE_SIZE,
    DEFAULT_SPACE_TYPE,
    RETRIEVED_PEOPLE_INFO_MSG,
    PEOPLE_API_NAME,
)

space_type = DEFAULT_SPACE_TYPE


class TestChatUtils(TestCase):
    @patch("google.authentication_utils.GoogleClientFactory.create_chat_client")
    def test_get_chat_spaces_success(self, mock_client):
        mock_spaces_response_page1 = {
            "spaces": [
                {"name": "spaces/space1", "displayName": "Space Name 1"},
                {"name": "spaces/space2", "displayName": "Space Name 2"},
            ],
            "nextPageToken": "next_page",
        }
        mock_spaces_response_page2 = {
            "spaces": [
                {"name": "spaces/space3", "displayName": "Space Name 3"},
            ],
            "nextPageToken": None,
        }

        mock_execute = (
            mock_client.return_value.spaces.return_value.list.return_value.execute
        )
        mock_execute.side_effect = [
            mock_spaces_response_page1,
            mock_spaces_response_page2,
        ]

        result = get_chat_spaces(space_type, DEFAULT_PAGE_SIZE)

        expected_result = {
            "space1": "Space Name 1",
            "space2": "Space Name 2",
            "space3": "Space Name 3",
        }
        self.assertEqual(result, expected_result)
        self.assertEqual(
            mock_client.return_value.spaces.return_value.list.call_count, 2
        )

        mock_client.return_value.spaces.return_value.list.assert_any_call(
            pageSize=DEFAULT_PAGE_SIZE,
            filter=f'space_type = "{space_type}"',
            pageToken=None,
        )
        mock_client.return_value.spaces.return_value.list.assert_any_call(
            pageSize=DEFAULT_PAGE_SIZE,
            filter=f'space_type = "{space_type}"',
            pageToken="next_page",
        )

    @patch("google.authentication_utils.GoogleClientFactory.create_chat_client")
    def test_get_chat_spaces_invalid_client(self, mock_client):
        mock_client.return_value = None

        with self.assertRaises(ValueError) as context:
            get_chat_spaces(space_type, DEFAULT_PAGE_SIZE)

        self.assertEqual(
            str(context.exception),
            NO_CLIENT_ERROR_MSG.format(client_name=CHAT_API_NAME),
        )

    def test_list_directory_all_people_ldap_success(self):
        mock_client = Mock()
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
        mock_client.people.return_value.listDirectoryPeople.return_value.execute.return_value = mock_people_response

        result = list_directory_all_people_ldap(mock_client)

        expected_result = {"id1": "user1", "id2": "user2"}
        self.assertEqual(result, expected_result)
        mock_client.people.return_value.listDirectoryPeople.assert_called_once_with(
            readMask="emailAddresses",
            pageSize=DEFAULT_PAGE_SIZE,
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageToken=None,
        )

    def test_list_directory_all_people_ldap_invalid_client(self):
        mock_client = None

        with self.assertRaises(ValueError) as context:
            list_directory_all_people_ldap(mock_client)
        self.assertEqual(
            str(context.exception),
            NO_CLIENT_ERROR_MSG.format(client_name=PEOPLE_API_NAME),
        )


if __name__ == "__main__":
    main()
