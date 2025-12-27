import unittest
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from http import HTTPStatus

from backend.historical_data.historical_controller import HistoricalController
from backend.common.api_endpoints import (
    MICROSOFT_BACKFILL_LDAPS_ENDPOINT,
    MICROSOFT_BACKFILL_CHAT_MESSAGES_ENDPOINT,
    JIRA_UPDATE_ISSUES_ENDPOINT,
    GOOGLE_CALENDAR_PULL_HISTORY_ENDPOINT,
    GERRIT_BACKFILL_CHANGES_ENDPOINT,
    GERRIT_BACKFILL_PROJECTS_ENDPOINT,
)
from backend.common.user_role import UserRole
from backend.utils.auth_middleware import AuthMiddleware


class TestHistoricalController(unittest.TestCase):
    def setUp(self):
        # Mock authentication service (middleware dependency)
        self.mock_auth_service = MagicMock()

        # Mock business services
        self.mock_ms_member_service = AsyncMock()
        self.mock_ms_chat_service = AsyncMock()
        self.mock_jira_service = MagicMock()
        self.mock_google_calendar_service = MagicMock()
        self.mock_datetime_utils = MagicMock()
        self.mock_gerrit_service = MagicMock()
        self.mock_google_chat_service = MagicMock()

        # Initialize controller with mocked services
        self.controller = HistoricalController(
            microsoft_member_sync_service=self.mock_ms_member_service,
            microsoft_chat_history_sync_service=self.mock_ms_chat_service,
            jira_history_sync_service=self.mock_jira_service,
            google_calendar_sync_service=self.mock_google_calendar_service,
            date_time_utils=self.mock_datetime_utils,
            gerrit_sync_service=self.mock_gerrit_service,
            google_chat_history_sync_service=self.mock_google_chat_service,
        )

        # Assemble FastAPI app
        self.app = FastAPI()
        # Add authentication middleware, otherwise requests will return 401
        self.app.add_middleware(AuthMiddleware, auth_service=self.mock_auth_service)
        self.app.include_router(self.controller.router)

        self.client = TestClient(self.app)
        self.headers = {"Authorization": "Bearer mock-token"}

    def _set_authenticated_user(self, roles=None):
        """Helper method to configure mock_auth_service to return a user with given roles."""
        if roles is None:
            roles = [UserRole.ADMIN]

        mock_user = MagicMock()
        mock_user.sub = "test_user_123"
        mock_user.roles = roles
        mock_user.primary_email = "admin@example.com"

        self.mock_auth_service.authenticate_request.return_value = mock_user

    def test_backfill_microsoft_ldaps_success(self):
        """Test Microsoft LDAPS backfill endpoint (ADMIN role)."""
        self._set_authenticated_user(roles=[UserRole.ADMIN])
        self.mock_ms_member_service.sync_microsoft_members_to_redis.return_value = None

        response = self.client.post(
            MICROSOFT_BACKFILL_LDAPS_ENDPOINT, headers=self.headers
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.json()["success"])

    def test_backfill_microsoft_chat_messages_success(self):
        """Test Microsoft chat messages backfill endpoint with path parameter."""
        self._set_authenticated_user(roles=[UserRole.ADMIN])
        chat_id = "test_chat_123"
        url = MICROSOFT_BACKFILL_CHAT_MESSAGES_ENDPOINT.format(chatId=chat_id)

        response = self.client.post(url, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.mock_ms_chat_service.sync_microsoft_chat_messages_by_chat_id.assert_called_once_with(
            chat_id
        )

    def test_update_jira_issues_with_query_param(self):
        """Test Jira update endpoint with query parameter (CRON_RUNNER role)."""
        self._set_authenticated_user(roles=[UserRole.CRON_RUNNER])
        hours = 5
        self.mock_jira_service.process_update_jira_issues.return_value = ["ISSUE-1"]

        response = self.client.post(
            f"{JIRA_UPDATE_ISSUES_ENDPOINT}?hours={hours}", headers=self.headers
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.mock_jira_service.process_update_jira_issues.assert_called_once_with(hours)

    def test_update_jira_issues_invalid_param(self):
        """Test Jira update endpoint with missing or invalid parameter (should return 400)."""
        self._set_authenticated_user(roles=[UserRole.ADMIN])

        response = self.client.post(JIRA_UPDATE_ISSUES_ENDPOINT, headers=self.headers)

        # Should pass auth check and return 400 from business logic
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_pull_calendar_history_with_body(self):
        """Test Google Calendar pull history endpoint with JSON body."""
        self._set_authenticated_user(roles=[UserRole.ADMIN])
        self.mock_datetime_utils.resolve_start_end_timestamps.return_value = (
            "ts1",
            "ts2",
        )

        payload = {"start_date": "2023-01-01", "end_date": "2023-01-02"}
        response = self.client.post(
            GOOGLE_CALENDAR_PULL_HISTORY_ENDPOINT, json=payload, headers=self.headers
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.mock_google_calendar_service.pull_calendar_history.assert_called_once_with(
            "ts1", "ts2"
        )

    def test_backfill_gerrit_changes_with_list_body(self):
        """Test Gerrit backfill endpoint with list parameter in request body."""
        self._set_authenticated_user(roles=[UserRole.ADMIN])
        payload = {"statuses": ["MERGED"]}

        response = self.client.post(
            GERRIT_BACKFILL_CHANGES_ENDPOINT, json=payload, headers=self.headers
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.mock_gerrit_service.fetch_and_store_changes.assert_called_once_with(
            statuses=["MERGED"]
        )

    def test_unauthorized_access(self):
        """Test access without required roles (should return 403 Forbidden)."""
        # Simulate a normal user without ADMIN or CRON_RUNNER role
        self._set_authenticated_user(roles=[UserRole.MENTORSHIP])

        response = self.client.post(
            GERRIT_BACKFILL_PROJECTS_ENDPOINT, headers=self.headers
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
