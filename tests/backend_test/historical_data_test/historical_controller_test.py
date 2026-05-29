import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from http import HTTPStatus

from backend.historical_data.historical_controller import HistoricalController
from backend.common.api_endpoints import (
    MICROSOFT_BACKFILL_LDAPS_ENDPOINT,
    MICROSOFT_BACKFILL_CHAT_MESSAGES_ENDPOINT,
    JIRA_SYNC_PROJECTS_ENDPOINT,
    JIRA_BACKFILL_ISSUES_ENDPOINT,
    JIRA_UPDATE_ISSUES_ENDPOINT,
    GOOGLE_CALENDAR_PULL_HISTORY_ENDPOINT,
    GERRIT_BACKFILL_CHANGES_ENDPOINT,
    GERRIT_BACKFILL_PROJECTS_ENDPOINT,
    GOOGLE_CHAT_SYNC_HISTORY_MESSAGES_ENDPOINT,
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

        # Mock async DB session + user identity service for middleware bootstrap
        mock_session = MagicMock()
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        begin_cm = MagicMock()
        begin_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        begin_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=begin_cm)
        self.mock_database = MagicMock()
        self.mock_database.session = MagicMock(return_value=session_cm)
        self.mock_user_identity_service = MagicMock()
        self.mock_user_identity_service.find_user_by_sub = AsyncMock(
            return_value=MagicMock(user_id=1)
        )

        # Assemble FastAPI app
        self.app = FastAPI()
        # Add authentication middleware, otherwise requests will return 401
        self.app.add_middleware(
            AuthMiddleware,
            auth_service=self.mock_auth_service,
            database=self.mock_database,
            user_identity_service=self.mock_user_identity_service,
            logger=MagicMock(),
        )
        self.app.include_router(self.controller.router)

        self.client = TestClient(self.app)
        self.headers = {"Authorization": "Bearer mock-token"}

    def _set_authenticated_user(self, roles=None):
        """Helper method to configure mock_auth_service to return a user with given roles."""
        if roles is None:
            roles = [UserRole.INFRA_ADMIN]

        mock_user = MagicMock()
        mock_user.sub = "test_user_123"
        mock_user.roles = roles
        mock_user.primary_email = "admin@example.com"

        self.mock_auth_service.authenticate_request.return_value = mock_user

    def test_backfill_microsoft_ldaps_success(self):
        """Test Microsoft LDAPS backfill endpoint (INFRA_ADMIN role)."""
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])
        self.mock_ms_member_service.sync_microsoft_members_to_redis.return_value = None

        response = self.client.post(
            MICROSOFT_BACKFILL_LDAPS_ENDPOINT, headers=self.headers
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.json()["success"])

    def test_backfill_microsoft_chat_messages_success(self):
        """Test Microsoft chat messages backfill endpoint with path parameter."""
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])
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
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])

        response = self.client.post(JIRA_UPDATE_ISSUES_ENDPOINT, headers=self.headers)

        # Should pass auth check and return 400 from business logic
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_pull_calendar_history_with_body(self):
        """Test Google Calendar pull history endpoint with JSON body."""
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])
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
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])
        payload = {"statuses": ["MERGED"]}

        response = self.client.post(
            GERRIT_BACKFILL_CHANGES_ENDPOINT, json=payload, headers=self.headers
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.mock_gerrit_service.fetch_and_store_changes.assert_called_once_with(
            statuses=["MERGED"]
        )

    def _assert_offloaded_once(self, spy_to_thread, target_callable):
        """Assert asyncio.to_thread was invoked exactly once for `target_callable`."""
        matching = [
            c
            for c in spy_to_thread.call_args_list
            if c.args and c.args[0] is target_callable
        ]
        self.assertEqual(len(matching), 1)

    def test_sync_google_chat_history_messages_offloads_to_thread(self):
        """sync_history_messages is a sync HTTP-heavy call; must run on a worker thread."""
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])

        with patch(
            "backend.historical_data.historical_controller.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as spy_to_thread:
            response = self.client.post(
                GOOGLE_CHAT_SYNC_HISTORY_MESSAGES_ENDPOINT, headers=self.headers
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self._assert_offloaded_once(
            spy_to_thread, self.mock_google_chat_service.sync_history_messages
        )

    def test_update_jira_issues_offloads_to_thread(self):
        """process_update_jira_issues is a sync JIRA HTTP call; must run on a worker thread."""
        self._set_authenticated_user(roles=[UserRole.CRON_RUNNER])

        with patch(
            "backend.historical_data.historical_controller.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as spy_to_thread:
            response = self.client.post(
                f"{JIRA_UPDATE_ISSUES_ENDPOINT}?hours=5", headers=self.headers
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self._assert_offloaded_once(
            spy_to_thread, self.mock_jira_service.process_update_jira_issues
        )

    def test_backfill_jira_issues_offloads_to_thread(self):
        """backfill_all_jira_issues is a sync JIRA HTTP call; must run on a worker thread."""
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])

        with patch(
            "backend.historical_data.historical_controller.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as spy_to_thread:
            response = self.client.post(
                JIRA_BACKFILL_ISSUES_ENDPOINT, headers=self.headers
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self._assert_offloaded_once(
            spy_to_thread, self.mock_jira_service.backfill_all_jira_issues
        )

    def test_sync_jira_projects_offloads_to_thread(self):
        """sync_jira_projects_id_and_name_mapping is a sync JIRA HTTP call; must run on a worker thread."""
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])

        with patch(
            "backend.historical_data.historical_controller.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as spy_to_thread:
            response = self.client.post(
                JIRA_SYNC_PROJECTS_ENDPOINT, headers=self.headers
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self._assert_offloaded_once(
            spy_to_thread,
            self.mock_jira_service.sync_jira_projects_id_and_name_mapping,
        )

    def test_pull_calendar_history_offloads_to_thread(self):
        """pull_calendar_history wraps Google Discovery .execute() and time.sleep; must offload."""
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])
        self.mock_datetime_utils.resolve_start_end_timestamps.return_value = (
            "ts1",
            "ts2",
        )

        with patch(
            "backend.historical_data.historical_controller.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as spy_to_thread:
            response = self.client.post(
                GOOGLE_CALENDAR_PULL_HISTORY_ENDPOINT,
                json={"start_date": "2023-01-01", "end_date": "2023-01-02"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self._assert_offloaded_once(
            spy_to_thread, self.mock_google_calendar_service.pull_calendar_history
        )

    def test_backfill_gerrit_changes_offloads_to_thread(self):
        """fetch_and_store_changes is a sync Gerrit HTTP call; must run on a worker thread."""
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])

        with patch(
            "backend.historical_data.historical_controller.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as spy_to_thread:
            response = self.client.post(
                GERRIT_BACKFILL_CHANGES_ENDPOINT,
                json={"statuses": ["MERGED"]},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self._assert_offloaded_once(
            spy_to_thread, self.mock_gerrit_service.fetch_and_store_changes
        )

    def test_backfill_gerrit_projects_offloads_to_thread(self):
        """sync_gerrit_projects is a sync Gerrit HTTP call; must run on a worker thread."""
        self._set_authenticated_user(roles=[UserRole.INFRA_ADMIN])

        with patch(
            "backend.historical_data.historical_controller.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as spy_to_thread:
            response = self.client.post(
                GERRIT_BACKFILL_PROJECTS_ENDPOINT, headers=self.headers
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self._assert_offloaded_once(
            spy_to_thread, self.mock_gerrit_service.sync_gerrit_projects
        )

    def test_unauthorized_access(self):
        """Test access without required roles (should return 403 Forbidden)."""
        # Simulate a normal user without INFRA_ADMIN or CRON_RUNNER role
        self._set_authenticated_user(roles=[UserRole.MENTORSHIP])

        response = self.client.post(
            GERRIT_BACKFILL_PROJECTS_ENDPOINT, headers=self.headers
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
