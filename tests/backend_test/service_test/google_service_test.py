from unittest import TestCase, main
from unittest.mock import MagicMock

from backend.service.google_service import GoogleService


class TestGoogleService(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_google_chat_client = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda fn: fn()

        self.service = GoogleService(
            logger=self.mock_logger,
            google_chat_client=self.mock_google_chat_client,
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


if __name__ == "__main__":
    main()
