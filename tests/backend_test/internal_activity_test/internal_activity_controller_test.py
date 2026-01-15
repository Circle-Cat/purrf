import unittest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from http import HTTPStatus

from backend.common.user_role import UserRole
from backend.common.api_endpoints import (
    MICROSOFT_LDAPS_ENDPOINT,
    MICROSOFT_CHAT_COUNT_ENDPOINT,
    MICROSOFT_CHAT_TOPICS_ENDPOINT,
    JIRA_PROJECTS_ENDPOINT,
    JIRA_BRIEF_ENDPOINT,
    JIRA_DETAIL_BATCH_ENDPOINT,
    GOOGLE_CALENDAR_LIST_ENDPOINT,
    GOOGLE_CALENDAR_EVENTS_ENDPOINT,
    GERRIT_STATS_ENDPOINT,
    GERRIT_PROJECTS_ENDPOINT,
    GOOGLE_CHAT_COUNT_ENDPOINT,
    GOOGLE_CHAT_SPACES_ENDPOINT,
    SUMMARY_ENDPOINT,
)
from backend.utils.auth_middleware import AuthMiddleware
from backend.internal_activity_service.internal_activity_controller import (
    InternalActivityController,
)


class TestInternalActivityControllerIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_auth_service = MagicMock()

        self.ldap_service = MagicMock()
        self.microsoft_chat_analytics_service = MagicMock()
        self.microsoft_meeting_chat_topic_cache_service = AsyncMock()
        self.jira_analytics_service = MagicMock()
        self.google_calendar_analytics_service = MagicMock()
        self.google_chat_analytics_service = MagicMock()
        self.date_time_util = MagicMock()
        self.gerrit_analytics_service = MagicMock()
        self.summary_service = MagicMock()

        self.controller = InternalActivityController(
            ldap_service=self.ldap_service,
            microsoft_chat_analytics_service=self.microsoft_chat_analytics_service,
            microsoft_meeting_chat_topic_cache_service=self.microsoft_meeting_chat_topic_cache_service,
            jira_analytics_service=self.jira_analytics_service,
            google_calendar_analytics_service=self.google_calendar_analytics_service,
            google_chat_analytics_service=self.google_chat_analytics_service,
            date_time_util=self.date_time_util,
            gerrit_analytics_service=self.gerrit_analytics_service,
            summary_service=self.summary_service,
        )

        self.app = FastAPI()
        self.app.add_middleware(AuthMiddleware, auth_service=self.mock_auth_service)
        self.app.include_router(self.controller.router)
        self.client = TestClient(self.app)

        self.headers = {"Authorization": "Bearer mock-token"}

    def _set_auth(self, roles: list[UserRole]):
        """Helper method to set mock user roles."""
        mock_user = MagicMock()
        mock_user.roles = roles
        self.mock_auth_service.authenticate_request.return_value = mock_user

    # Microsoft API tests

    def test_get_ldaps_and_names(self):
        """Test MICROSOFT_LDAPS_ENDPOINT (GET)."""
        self._set_auth([UserRole.CC_INTERNAL])
        self.ldap_service.get_ldaps_by_status_and_group.return_value = {"data": "test"}

        path = MICROSOFT_LDAPS_ENDPOINT.replace("{status}", "active")
        response = self.client.get(
            f"{path}?groups[]=interns&groups[]=employees",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.ldap_service.get_ldaps_by_status_and_group.assert_called_once()

    def test_count_microsoft_chat_messages(self):
        """Test MICROSOFT_CHAT_COUNT_ENDPOINT (POST)."""
        self._set_auth([UserRole.ADMIN])
        payload = {"ldaps": ["a"], "startDate": "2023-01-01"}
        response = self.client.post(
            MICROSOFT_CHAT_COUNT_ENDPOINT,
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.microsoft_chat_analytics_service.count_microsoft_chat_messages_in_date_range.assert_called_once()

    def test_all_microsoft_chat_topics(self):
        """Test MICROSOFT_CHAT_TOPICS_ENDPOINT (GET)."""
        self._set_auth([UserRole.ADMIN])
        self.microsoft_meeting_chat_topic_cache_service.get_microsoft_chat_topics.return_value = []
        response = self.client.get(MICROSOFT_CHAT_TOPICS_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.microsoft_meeting_chat_topic_cache_service.get_microsoft_chat_topics.assert_called_once()

    # Jira API tests

    def test_get_all_jira_projects_api(self):
        """Test JIRA_PROJECTS_ENDPOINT (GET)."""
        self._set_auth([UserRole.ADMIN])
        response = self.client.get(JIRA_PROJECTS_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.jira_analytics_service.get_all_jira_projects.assert_called_once()

    def test_get_jira_brief(self):
        """Test JIRA_BRIEF_ENDPOINT (POST)."""
        self._set_auth([UserRole.ADMIN])
        payload = {"statusList": ["done"], "startDate": "2023-01-01"}
        response = self.client.post(
            JIRA_BRIEF_ENDPOINT,
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.jira_analytics_service.get_issues_summary.assert_called_once()

    def test_get_issue_detail_batch(self):
        """Test JIRA_DETAIL_BATCH_ENDPOINT (POST)."""
        self._set_auth([UserRole.ADMIN])
        payload = {"issueIds": ["ISSUE-1"]}
        response = self.client.post(
            JIRA_DETAIL_BATCH_ENDPOINT,
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.jira_analytics_service.process_get_issue_detail_batch.assert_called_once()

    # Google Calendar API tests

    def test_get_all_calendars_api(self):
        """Test GOOGLE_CALENDAR_LIST_ENDPOINT (GET)."""
        self._set_auth([UserRole.ADMIN])
        response = self.client.get(GOOGLE_CALENDAR_LIST_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.google_calendar_analytics_service.get_all_calendars.assert_called_once()

    def test_get_all_events_api(self):
        """Test GOOGLE_CALENDAR_EVENTS_ENDPOINT (POST)."""
        self._set_auth([UserRole.ADMIN])
        self.date_time_util.get_start_end_timestamps.return_value = (None, None)
        payload = {
            "calendarIds": ["cal1"],
            "startDate": "2023-01-01",
            "ldaps": ["user1"],
        }
        response = self.client.post(
            GOOGLE_CALENDAR_EVENTS_ENDPOINT,
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.google_calendar_analytics_service.get_all_events_from_calendars.assert_called_once()

    # Gerrit API tests

    def test_get_gerrit_stats(self):
        """Test GERRIT_STATS_ENDPOINT (POST)."""
        self._set_auth([UserRole.ADMIN])
        payload = {"ldaps": ["user1"]}
        response = self.client.post(
            GERRIT_STATS_ENDPOINT,
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.gerrit_analytics_service.get_gerrit_stats.assert_called_once()

    def test_get_gerrit_projects(self):
        """Test GERRIT_PROJECTS_ENDPOINT (GET)."""
        self._set_auth([UserRole.ADMIN])
        response = self.client.get(GERRIT_PROJECTS_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.gerrit_analytics_service.get_gerrit_projects.assert_called_once()

    # Google Chat API tests

    def test_get_google_chat_messages_count(self):
        """Test GOOGLE_CHAT_COUNT_ENDPOINT (POST)."""
        self._set_auth([UserRole.ADMIN])
        payload = {"spaceIds": ["s1"]}
        response = self.client.post(
            GOOGLE_CHAT_COUNT_ENDPOINT,
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.google_chat_analytics_service.count_messages.assert_called_once()

    def test_get_chat_spaces_route(self):
        """Test GOOGLE_CHAT_SPACES_ENDPOINT (GET)."""
        self._set_auth([UserRole.ADMIN])
        response = self.client.get(
            f"{GOOGLE_CHAT_SPACES_ENDPOINT}?spaceType=SPACE",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.google_chat_analytics_service.get_chat_spaces_by_type.assert_called_with(
            "SPACE"
        )

    # Summary API tests (role-based)

    def test_get_summary_success(self):
        """Test SUMMARY_ENDPOINT (POST) with CC_INTERNAL permission."""
        self._set_auth([UserRole.CC_INTERNAL])
        payload = {
            "startDate": "2023-01-01",
            "includeTerminated": True,
            "groups": ["employees"],
        }
        response = self.client.post(
            SUMMARY_ENDPOINT,
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.summary_service.get_summary.assert_called_once()

    # Authorization enforcement tests

    def test_forbidden_access(self):
        """Verify that non-admin users are forbidden from accessing admin endpoints."""
        self._set_auth([UserRole.MENTORSHIP])

        response = self.client.get(JIRA_PROJECTS_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.jira_analytics_service.get_all_jira_projects.assert_not_called()


if __name__ == "__main__":
    unittest.main()
