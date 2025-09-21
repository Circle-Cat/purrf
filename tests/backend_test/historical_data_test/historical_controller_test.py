from http import HTTPStatus
from unittest import TestCase, main, IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock, MagicMock
from flask import Flask
from backend.historical_data.historical_controller import (
    history_bp,
    HistoricalController,
)


MICROSOFT_LDAP_FETCHER_API = "/microsoft/backfill/ldaps"
MICROSOFT_CHAT_FETCHER_API = "/microsoft/fetch/history/messages/{chat_id}"
GOOGLE_CHAT_FETCHER_API = "/api/google/chat/spaces/messages"
GOOGLE_CALENDAR_FETCHER_API = "/api/google/calendar/history/pull"
JIRA_UPDATE_API = "/api/jira/update"
JIRA_BACKFILL_API = "/api/jira/backfill"
JIRA_PROJECT_API = "/api/jira/project"
TEST_CHAT_ID = "chat131"
GERRIT_FETCHER_API = "/gerrit/backfill"
GERRIT_PROJECTS_BACKFILL_API = "/gerrit/projects/backfill"


# /microsoft/backfill/chat/messages/<chatId>
class TestHistoricalController(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.microsoft_member_sync_service = AsyncMock()
        self.microsoft_member_sync_service.sync_microsoft_members_to_redis = AsyncMock()
        self.microsoft_chat_history_sync_service = AsyncMock()
        self.microsoft_chat_history_sync_service.sync_microsoft_chat_messages_by_chat_id = AsyncMock()
        self.mock_jira_service = MagicMock()
        self.google_calendar_sync_service = MagicMock()
        self.date_time_utils = MagicMock()
        self.gerrit_sync_service = AsyncMock()
        self.gerrit_sync_service.fetch_and_store_changes = AsyncMock()
        self.gerrit_sync_service.sync_gerrit_projects = MagicMock()
        self.controller = HistoricalController(
            microsoft_member_sync_service=self.microsoft_member_sync_service,
            microsoft_chat_history_sync_service=self.microsoft_chat_history_sync_service,
            jira_history_sync_service=self.mock_jira_service,
            google_calendar_sync_service=self.google_calendar_sync_service,
            date_time_utils=self.date_time_utils,
            gerrit_sync_service=self.gerrit_sync_service,
        )

        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

    async def asyncTearDown(self):
        self.app_context.pop()

    def test_backfill_jira_issues(self):
        mock_result = 5
        self.mock_jira_service.backfill_all_jira_issues.return_value = mock_result

        with self.app.test_request_context(JIRA_PROJECT_API, method="POST"):
            response = self.controller.backfill_jira_issues()

        self.mock_jira_service.backfill_all_jira_issues.assert_called_once()
        self.assertEqual(response.status_code, HTTPStatus.OK)

    async def test_backfill_microsoft_ldaps_success(self):
        with self.app.test_request_context(
            MICROSOFT_LDAP_FETCHER_API,
            method="POST",
            content_type="application/json",
        ):
            response = await self.controller.backfill_microsoft_ldaps()

        self.microsoft_member_sync_service.sync_microsoft_members_to_redis.assert_called_once()

        self.assertEqual(response.status_code, HTTPStatus.OK)

    async def test_backfill_microsoft_chat_messages(self):
        with self.app.test_request_context(
            MICROSOFT_CHAT_FETCHER_API.format(chat_id=TEST_CHAT_ID),
            method="POST",
            content_type="application/json",
        ):
            response = await self.controller.backfill_microsoft_chat_messages(
                TEST_CHAT_ID
            )

        self.microsoft_chat_history_sync_service.sync_microsoft_chat_messages_by_chat_id.assert_called_once()
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_sync_jira_projects(self):
        mock_result = 5
        self.mock_jira_service.sync_jira_projects_id_and_name_mapping.return_value = (
            mock_result
        )

        with self.app.test_request_context(JIRA_PROJECT_API, method="POST"):
            response = self.controller.sync_jira_projects()

        self.mock_jira_service.sync_jira_projects_id_and_name_mapping.assert_called_once()

        expected_json = {
            "message": "Imported successfully",
            "data": {"imported_projects": mock_result},
        }

        self.assertEqual(response.get_json(), expected_json)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_update_jira_issues(self):
        mock_result = 5
        self.mock_jira_service.process_update_jira_issues.return_value = mock_result

        with self.app.test_request_context(
            JIRA_UPDATE_API, method="POST", query_string={"hours": 24}
        ):
            response = self.controller.update_jira_issues()

        self.mock_jira_service.process_update_jira_issues.assert_called_once()
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_pull_calendar_history_success(self):
        self.controller.date_time_utils.resolve_start_end_timestamps = MagicMock(
            return_value=("2023-09-01T00:00:00Z", "2023-09-02T00:00:00Z")
        )
        self.controller.google_calendar_sync_service.pull_calendar_history = MagicMock()

        with self.app.test_request_context(
            GOOGLE_CALENDAR_FETCHER_API,
            method="POST",
            content_type="application/json",
        ):
            response = self.controller.pull_calendar_history_api()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("Google Calendar history pulled", response.json["message"])
        self.controller.google_calendar_sync_service.pull_calendar_history.assert_called_once_with(
            "2023-09-01T00:00:00Z", "2023-09-02T00:00:00Z"
        )

    async def test_backfill_gerrit_changes_success(self):
        with self.app.test_request_context(
            GERRIT_FETCHER_API,
            method="POST",
            content_type="application/json",
        ):
            response = await self.controller.backfill_gerrit_changes()

        self.gerrit_sync_service.fetch_and_store_changes.assert_called_once()

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_backfill_gerrit_projects_success(self):
        """Tests the successful backfill of Gerrit projects."""
        mock_project_count = 10
        self.gerrit_sync_service.sync_gerrit_projects.return_value = mock_project_count

        with self.app.test_request_context(
            GERRIT_PROJECTS_BACKFILL_API,
            method="POST",
            content_type="application/json",
        ):
            response = self.controller.backfill_gerrit_projects()

        self.gerrit_sync_service.sync_gerrit_projects.assert_called_once()
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_data = response.get_json()
        self.assertEqual(
            response_data["message"],
            f"Successfully synced {mock_project_count} Gerrit projects.",
        )
        self.assertEqual(response_data["data"]["project_count"], mock_project_count)


class TestAppRoutes(TestCase):
    @classmethod
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(history_bp)
        self.client = app.test_client()
        app.testing = True

    @patch("backend.historical_data.historical_controller.fetch_history_messages")
    def test_history_messages(self, mock_fetch_history_messages):
        mock_result = {"saved_messages_count": 3, "total_messges_count": 5}
        mock_fetch_history_messages.return_value = mock_result

        response = self.client.post(GOOGLE_CHAT_FETCHER_API)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)

        mock_fetch_history_messages.assert_called_once()


if __name__ == "__main__":
    main()
