from unittest import TestCase, main
from unittest.mock import MagicMock

from backend.service.google_service import GoogleService


class TestGoogleService(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_google_chat_client = MagicMock()
        self.mock_google_people_client = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda fn: fn()

        self.service = GoogleService(
            logger=self.mock_logger,
            google_chat_client=self.mock_google_chat_client,
            google_people_client=self.mock_google_people_client,
            retry_utils=self.mock_retry_utils,
        )

    def test_get_chat_spaces_success_single_page(self):
        """
        Tests successful retrieval of chat spaces from a single API page.
        """
        mock_response = {
            "spaces": [
                {"name": "spaces/space1", "displayName": "Space Name 1"},
                {"name": "spaces/space2", "displayName": "Space Name 2"},
            ],
            "nextPageToken": None,
        }
        self.mock_google_chat_client.spaces.return_value.list.return_value.execute.return_value = mock_response

        result = self.service.get_chat_spaces(space_type="SPACE")

        expected_result = {
            "space1": "Space Name 1",
            "space2": "Space Name 2",
        }
        self.assertEqual(result, expected_result)
        self.mock_google_chat_client.spaces.return_value.list.assert_called_once_with(
            filter='space_type = "SPACE"',
            pageToken=None,
        )
        self.mock_google_chat_client.spaces.return_value.list.return_value.execute.assert_called_once()
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_get_chat_spaces_success_multiple_pages(self):
        """
        Tests successful retrieval of chat spaces spanning multiple API pages.
        """
        mock_response_page1 = {
            "spaces": [
                {"name": "spaces/space1", "displayName": "Space Name 1"},
            ],
            "nextPageToken": "next_page_token_123",
        }
        mock_response_page2 = {
            "spaces": [
                {"name": "spaces/space2", "displayName": "Space Name 2"},
            ],
            "nextPageToken": None,
        }

        execute_mock = MagicMock(side_effect=[mock_response_page1, mock_response_page2])
        self.mock_google_chat_client.spaces.return_value.list.return_value.execute = (
            execute_mock
        )

        result = self.service.get_chat_spaces(space_type="ROOM")

        expected_result = {
            "space1": "Space Name 1",
            "space2": "Space Name 2",
        }
        self.assertEqual(result, expected_result)

        list_mock = self.mock_google_chat_client.spaces.return_value.list
        self.assertEqual(list_mock.call_count, 2)
        self.assertEqual(execute_mock.call_count, 2)
        self.assertEqual(self.mock_retry_utils.get_retry_on_transient.call_count, 2)

    def test_get_chat_spaces_api_error_raises_runtime_error(self):
        """
        Tests that a RuntimeError is raised when the API call fails.
        """
        test_exception = Exception("API is down")
        self.mock_retry_utils.get_retry_on_transient.side_effect = test_exception

        with self.assertRaises(RuntimeError):
            self.service.get_chat_spaces(space_type="SPACE")

        self.mock_logger.error.assert_called_once()

    def test_get_chat_spaces_missing_spaces_field_raises_value_error(self):
        """
        Tests that a ValueError is raised if the 'spaces' field is missing from the API response.
        """
        mock_response = {"nextPageToken": None}
        self.mock_google_chat_client.spaces.return_value.list.return_value.execute.return_value = mock_response

        with self.assertRaises(ValueError):
            self.service.get_chat_spaces(space_type="SPACE")

    def test_list_directory_all_people_ldap_success_single_page(self):
        """
        Tests successful retrieval of directory people from a single API page.
        """
        mock_response = {
            "people": [
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "123"}},
                            "value": "user1@example.com",
                        }
                    ]
                },
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "456"}},
                            "value": "user2@example.com",
                        }
                    ]
                },
            ],
            "nextPageToken": None,
        }
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute.return_value = mock_response

        result = self.service.list_directory_all_people_ldap()

        expected_result = {
            "123": "user1",
            "456": "user2",
        }
        self.assertEqual(result, expected_result)
        self.mock_google_people_client.people.return_value.listDirectoryPeople.assert_called_once_with(
            readMask="emailAddresses",
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageToken=None,
        )
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute.assert_called_once()
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_list_directory_all_people_ldap_success_multiple_pages(self):
        """
        Tests successful retrieval of directory people spanning multiple API pages.
        """
        mock_response_page1 = {
            "people": [
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "123"}},
                            "value": "user1@example.com",
                        }
                    ]
                }
            ],
            "nextPageToken": "next_page_token_abc",
        }
        mock_response_page2 = {
            "people": [
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "456"}},
                            "value": "user2@example.com",
                        }
                    ]
                }
            ],
            "nextPageToken": None,
        }

        execute_mock = MagicMock(side_effect=[mock_response_page1, mock_response_page2])
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute = execute_mock

        result = self.service.list_directory_all_people_ldap()

        expected_result = {
            "123": "user1",
            "456": "user2",
        }
        self.assertEqual(result, expected_result)

        list_mock = (
            self.mock_google_people_client.people.return_value.listDirectoryPeople
        )
        self.assertEqual(list_mock.call_count, 2)
        self.assertEqual(execute_mock.call_count, 2)
        self.assertEqual(self.mock_retry_utils.get_retry_on_transient.call_count, 2)

    def test_list_directory_all_people_ldap_api_error_raises_runtime_error(self):
        """
        Tests that a RuntimeError is raised when the API call fails.
        """
        test_exception = Exception("API is down")
        self.mock_retry_utils.get_retry_on_transient.side_effect = test_exception

        with self.assertRaises(RuntimeError):
            self.service.list_directory_all_people_ldap()

        self.mock_logger.error.assert_called_once()

    def test_list_directory_all_people_ldap_missing_people_field(self):
        """
        Tests retrieval when API response contains an empty 'people' list.
        """
        mock_response = {"people": [], "nextPageToken": None}
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute.return_value = mock_response

        result = self.service.list_directory_all_people_ldap()

        self.assertEqual(result, {})

    def test_list_directory_all_people_ldap_handles_malformed_data(self):
        """
        Tests that malformed or incomplete person data in the response is handled gracefully.
        """
        mock_response = {
            "people": [
                # Valid person
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "123"}},
                            "value": "user1@example.com",
                        }
                    ]
                },
                # Person with no emailAddresses
                {"resourceName": "people/c2"},
                # Person with empty emailAddresses list
                {"emailAddresses": []},
                # Person with email but no source id
                {
                    "emailAddresses": [
                        {"metadata": {"source": {}}, "value": "user2@example.com"}
                    ]
                },
                # Person with id but no email value
                {"emailAddresses": [{"metadata": {"source": {"id": "456"}}}]},
                # Person with invalid email value
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "789"}},
                            "value": "user3_no_at_sign",
                        }
                    ]
                },
            ],
            "nextPageToken": None,
        }
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute.return_value = mock_response

        result = self.service.list_directory_all_people_ldap()

        # Only the valid person should be in the result
        expected_result = {"123": "user1"}
        self.assertEqual(result, expected_result)


if __name__ == "__main__":
    main()
