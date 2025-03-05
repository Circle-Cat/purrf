import unittest
from unittest.mock import Mock
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


class TestChatUtils(unittest.TestCase):
    def setUp(self):
        self.log_capture_string = StringIO()
        ch = logging.StreamHandler(self.log_capture_string)
        from tools.log.logger import setup_logger

        setup_logger()
        root_logger = logging.getLogger()
        ch.setFormatter(root_logger.handlers[0].formatter)
        logging.getLogger().addHandler(ch)
        logging.getLogger().setLevel(logging.DEBUG)

    def tearDown(self):
        logging.getLogger().handlers = []

    def test_get_chat_spaces_success(self):
        mock_client = Mock()
        mock_spaces_response = {
            "spaces": [
                {"name": "spaces/space1", "displayName": "Space Name 1"},
                {"name": "spaces/space2", "displayName": "Space Name 2"},
            ],
            "nextPageToken": None,
        }
        mock_client.spaces.return_value.list.return_value.execute.return_value = (
            mock_spaces_response
        )

        result = get_chat_spaces(mock_client, space_type, DEFAULT_PAGE_SIZE)

        expected_result = {"space1": "Space Name 1", "space2": "Space Name 2"}
        self.assertEqual(result, expected_result)
        mock_client.spaces.return_value.list.assert_called_once_with(
            pageSize=DEFAULT_PAGE_SIZE,
            filter=f'space_type = "{space_type}"',
            pageToken=None,
        )
        log_output = self.log_capture_string.getvalue()
        self.assertIn(
            RETRIEVED_SPACES_INFO_MSG.format(count=2, space_type=space_type), log_output
        )

    def test_get_chat_spaces_invalid_client(self):
        mock_client = None

        with self.assertRaises(ValueError) as context:
            get_chat_spaces(mock_client, space_type, DEFAULT_PAGE_SIZE)
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
        log_output = self.log_capture_string.getvalue()
        self.assertIn(RETRIEVED_PEOPLE_INFO_MSG.format(count=2), log_output)
        self.assertNotIn(
            NO_CLIENT_ERROR_MSG.format(client_name=PEOPLE_API_NAME), log_output
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
    unittest.main()
