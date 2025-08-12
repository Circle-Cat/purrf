from unittest import TestCase, main
from unittest.mock import Mock, patch
from backend.utils.google_chat_utils import get_chat_spaces

TEST_SPACE_TYPE = "spaces"
DEFAULT_PAGE_SIZE = 1000


class TestGoogleChatUtils(TestCase):
    @patch("backend.common.google_client.GoogleClientFactory.create_chat_client")
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
        result = get_chat_spaces(TEST_SPACE_TYPE, DEFAULT_PAGE_SIZE)
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
            filter='space_type = "spaces"',
            pageToken=None,
        )
        mock_client.return_value.spaces.return_value.list.assert_any_call(
            pageSize=DEFAULT_PAGE_SIZE,
            filter='space_type = "spaces"',
            pageToken="next_page",
        )

    @patch("backend.common.google_client.GoogleClientFactory.create_chat_client")
    def test_get_chat_spaces_invalid_client(self, mock_client):
        mock_client.return_value = None
        with self.assertRaises(ValueError) as context:
            get_chat_spaces(TEST_SPACE_TYPE, DEFAULT_PAGE_SIZE)

    @patch("backend.common.google_client.GoogleClientFactory.create_chat_client")
    def test_get_chat_spaces_empty_result_raises_error(self, mock_client):
        mock_execute = (
            mock_client.return_value.spaces.return_value.list.return_value.execute
        )
        mock_execute.return_value = {"spaces": [], "nextPageToken": None}
        with self.assertRaises(ValueError) as context:
            get_chat_spaces(TEST_SPACE_TYPE, DEFAULT_PAGE_SIZE)


if __name__ == "__main__":
    main()
