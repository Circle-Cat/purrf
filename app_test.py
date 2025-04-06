"""Test for purrf"""

import http.client
from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import patch

from app import app


FETCH_HISTORY_MESSAGES_API = "/api/chat/spaces/messages"
HEALTH_API = "/health"


class TestAppRoutes(TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.testing = True

    @patch("google.google_api.executor.submit")
    @patch("google.google_api.fetch_history_messages")
    def test_history_messages_integration(self, mock_fetch, mock_submit):
        response = self.client.post(FETCH_HISTORY_MESSAGES_API)

        self.assertEqual(response.status_code, http.client.ACCEPTED)

        mock_submit.assert_called_once_with(mock_fetch)

    @patch("google.google_api.executor.submit", side_effect=Exception())
    def test_history_messages_error(self, mock_submit):
        response = self.client.post(FETCH_HISTORY_MESSAGES_API)
        self.assertEqual(response.status_code, http.client.INTERNAL_SERVER_ERROR)

    def test_health_check(self):
        """Testing health check endpoint"""
        response = self.client.get(HEALTH_API)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json, {"status": "success"})


if __name__ == "__main__":
    main()
