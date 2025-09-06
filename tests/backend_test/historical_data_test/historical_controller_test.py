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
JIRA_UPDATE_API = "/api/jira/update"
JIRA_BACKFILL_API = "/api/jira/backfill"
JIRA_PROJECT_API = "/api/jira/project"
TEST_CHAT_ID = "chat131"


# /microsoft/backfill/chat/messages/<chatId>
class TestHistoricalController(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.microsoft_member_sync_service = AsyncMock()
        self.microsoft_member_sync_service.sync_microsoft_members_to_redis = AsyncMock()
        self.microsoft_chat_history_sync_service = AsyncMock()
        self.microsoft_chat_history_sync_service.sync_microsoft_chat_messages_by_chat_id = AsyncMock()

        self.mock_jira_service = MagicMock()
        self.controller = HistoricalController(
            microsoft_member_sync_service=self.microsoft_member_sync_service,
            microsoft_chat_history_sync_service=self.microsoft_chat_history_sync_service,
            jira_history_sync_service=self.mock_jira_service,
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

    @patch("backend.historical_data.historical_controller.pull_calendar_history")
    def test_pull_calendar_history_success(self, mock_pull_calendar_history):
        mock_pull_calendar_history.return_value = None

        response = self.client.post("/api/google/calendar/history/pull", json={})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("Google Calendar history pulled", response.json["message"])

        args, _ = mock_pull_calendar_history.call_args
        self.assertEqual(len(args), 2)
        self.assertTrue(isinstance(args[0], str))
        self.assertTrue(isinstance(args[1], str))


if __name__ == "__main__":
    main()
