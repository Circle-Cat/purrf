from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import patch
from flask import Flask
from src.historical_data.historical_api import history_bp
from src.common.constants import MicrosoftAccountStatus


MICROSOFT_LDAP_FETCHER_API = "/api/microsoft/backfill/ldaps"
MICROSOFT_CHAT_FETCHER_API = "/microsoft/fetch/history/messages/{chat_id}"
GOOGLE_CHAT_FETCHER_API = "/api/google/chat/spaces/messages"
JIRA_BACKFILL_API = "/api/jira/backfill"
JIRA_PROJECT_API = "/api/jira/project"
TEST_CHAT_ID = "chat131"


class TestAppRoutes(TestCase):
    @classmethod
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(history_bp)
        self.client = app.test_client()
        app.testing = True

    @patch("src.historical_data.historical_api.sync_microsoft_members_to_redis")
    def test_backfill_microsoft_ldaps(self, mock_sync_microsoft_members_to_redis):
        mock_result = {
            MicrosoftAccountStatus.ACTIVE.value: 3,
            MicrosoftAccountStatus.TERMINATED.value: 2,
        }
        mock_sync_microsoft_members_to_redis.return_value = mock_result

        response = self.client.post(MICROSOFT_LDAP_FETCHER_API)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)

        mock_sync_microsoft_members_to_redis.assert_called_once()

    @patch("src.historical_data.historical_api.sync_microsoft_chat_messages_by_chat_id")
    def backfill_microsoft_chat_messages(
        self, mock_sync_microsoft_chat_messages_by_chat_id
    ):
        mock_result = {"total_processed": 5, "total_skipped": 0}
        mock_sync_microsoft_members_to_redis.return_value = mock_result

        response = self.client.post(
            MICROSOFT_CHAT_FETCHER_API.format(chat_id=TEST_CHAT_ID)
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)

        mock_sync_microsoft_chat_messages_by_chat_id.assert_called_once()

    @patch("src.historical_data.historical_api.fetch_history_messages")
    def test_history_messages(self, mock_fetch_history_messages):
        mock_result = {"saved_messages_count": 3, "total_messges_count": 5}
        mock_fetch_history_messages.return_value = mock_result

        response = self.client.post(GOOGLE_CHAT_FETCHER_API)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)

        mock_fetch_history_messages.assert_called_once()

    @patch("src.historical_data.historical_api.process_backfill_jira_issues")
    def test_backfill_jira_issues(self, mock_process_backfill_jira_issues):
        mock_result = 150
        mock_process_backfill_jira_issues.return_value = mock_result

        response = self.client.post(JIRA_BACKFILL_API)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_data = response.get_json()
        self.assertEqual(response_data["data"]["imported_issues"], 150)

        mock_process_backfill_jira_issues.assert_called_once()

    @patch("src.historical_data.historical_api.process_sync_jira_projects")
    def test_sync_jira_projects(self, mock_process_sync_jira_projects):
        mock_result = 5
        mock_process_sync_jira_projects.return_value = mock_result

        response = self.client.post(JIRA_PROJECT_API)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], {"imported_projects": mock_result})
        self.assertEqual(response.json["message"], "Imported successfully")

        mock_process_sync_jira_projects.assert_called_once()

    @patch("src.historical_data.historical_api.pull_calendar_history")
    def test_pull_calendar_history_success(self, mock_pull_calendar_history):
        mock_pull_calendar_history.return_value = None

        response = self.client.post("/api/google/calendar/history/pull", json={})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("Google Calendar history pulled", response.json["message"])

        args, kwargs = mock_pull_calendar_history.call_args
        self.assertEqual(len(args), 2)
        self.assertTrue(isinstance(args[0], str))
        self.assertTrue(isinstance(args[1], str))


if __name__ == "__main__":
    main()
