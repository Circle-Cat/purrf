"""Test for purrf"""

import http.client
from unittest import TestCase, main
from unittest.mock import patch

from app import app


FETCH_HISTORY_MESSAGES_API = "/api/chat/spaces/messages"


class TestAppRoutes(TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.testing = True

    @patch("google.google_api.executor.submit")
    @patch("google.google_api.fetch_history_messages")
    def test_history_messages_integration(self, mock_fetch, mock_submit):
        response = self.client.get(FETCH_HISTORY_MESSAGES_API)

        self.assertEqual(response.status_code, http.client.ACCEPTED)

        mock_submit.assert_called_once_with(mock_fetch)

    @patch("google.google_api.executor.submit", side_effect=Exception())
    def test_history_messages_error(self, mock_submit):
        response = self.client.get(FETCH_HISTORY_MESSAGES_API)
        self.assertEqual(response.status_code, http.client.INTERNAL_SERVER_ERROR)


if __name__ == "__main__":
    main()
