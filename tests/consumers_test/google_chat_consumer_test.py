from unittest import TestCase, main
from unittest.mock import Mock, patch
from src.consumers.google_chat_consumer import get_ldap_by_id


class TestChatUtils(TestCase):
    @patch(
        "src.consumers.google_chat_consumer.GoogleClientFactory.create_people_client"
    )
    def test_get_ldap_by_id_success(self, mock_client):
        mock_people_service = mock_client.return_value
        mock_get = mock_people_service.people.return_value.get.return_value.execute

        mock_get.return_value = {"emailAddresses": [{"value": "test.user@example.com"}]}

        result = get_ldap_by_id("12345")
        self.assertEqual(result, "test.user")

        mock_people_service.people.return_value.get.assert_called_once_with(
            resourceName="people/12345", personFields="emailAddresses"
        )

    @patch(
        "src.consumers.google_chat_consumer.GoogleClientFactory.create_people_client"
    )
    def test_get_ldap_by_id_no_email(self, mock_client):
        mock_people_service = mock_client.return_value
        mock_get = mock_people_service.people.return_value.get.return_value.execute

        mock_get.return_value = {"emailAddresses": []}

        result = get_ldap_by_id("12345")
        self.assertIsNone(result)

    @patch(
        "src.consumers.google_chat_consumer.GoogleClientFactory.create_people_client"
    )
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
