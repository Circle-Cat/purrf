from unittest import TestCase, main
from unittest.mock import Mock, patch
import logging
from io import StringIO
from google.chat_utils import get_ldap_by_id
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
