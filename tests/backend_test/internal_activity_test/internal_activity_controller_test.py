import unittest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from http import HTTPStatus

from backend.common.identity_type import IdentityType
from backend.common.permissions import Permission
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
    MY_SUMMARY_ENDPOINT,
)
from backend.utils.auth_middleware import AuthMiddleware
from backend.internal_activity_service.internal_activity_controller import (
    InternalActivityController,
)
from backend.dto.internal_activity_summary_response_dto import ActivitySummaryDto


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
        self.launchdarkly_service = MagicMock()

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
            launchdarkly_service=self.launchdarkly_service,
        )

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
            return_value=MagicMock(user_id=1, is_super_admin=False)
        )
        self.mock_user_permissions_repository = MagicMock()
        self.mock_user_permissions_repository.get_active_permission_names = AsyncMock(
            return_value=[]
        )

        self.app = FastAPI()
        self.app.add_middleware(
            AuthMiddleware,
            auth_service=self.mock_auth_service,
            database=self.mock_database,
            user_identity_service=self.mock_user_identity_service,
            user_permissions_repository=self.mock_user_permissions_repository,
            logger=MagicMock(),
        )
        self.app.include_router(self.controller.router)
        self.client = TestClient(self.app)

        self.headers = {"Authorization": "Bearer mock-token"}

    def _set_auth(self, permissions: list[Permission]):
        """Resolve the request user to the given permissions via the middleware."""
        mock_user = MagicMock()
        mock_user.is_service_account = False
        mock_user.is_super_admin = False
        mock_user.last_login_at = None
        # A non-passwordless sub keeps is_rowless_login False, so the middleware
        # resolves the user via the mocked sub-routed find_user_by_sub instead of
        # the (unmocked) row-less create_or_swap_user path.
        mock_user.sub = "google-oauth2|test-user"
        mock_user.identity_type = IdentityType.INTERNAL
        self.mock_auth_service.authenticate_request.return_value = mock_user
        self.mock_user_permissions_repository.get_active_permission_names.return_value = [
            p.value for p in permissions
        ]

    # Microsoft API tests

    def test_get_ldaps_and_names(self):
        """Test MICROSOFT_LDAPS_ENDPOINT (GET)."""
        self._set_auth([Permission.DIRECTORY_MICROSOFT_LDAP_READ])
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
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
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
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
        self.microsoft_meeting_chat_topic_cache_service.get_microsoft_chat_topics.return_value = []
        response = self.client.get(MICROSOFT_CHAT_TOPICS_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.microsoft_meeting_chat_topic_cache_service.get_microsoft_chat_topics.assert_called_once()

    # Jira API tests

    def test_get_all_jira_projects_api(self):
        """Test JIRA_PROJECTS_ENDPOINT (GET)."""
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
        response = self.client.get(JIRA_PROJECTS_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.jira_analytics_service.get_all_jira_projects.assert_called_once()

    def test_get_jira_brief(self):
        """Test JIRA_BRIEF_ENDPOINT (POST)."""
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
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
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
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
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
        response = self.client.get(GOOGLE_CALENDAR_LIST_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.google_calendar_analytics_service.get_all_calendars.assert_called_once()

    def test_get_all_events_api(self):
        """Test GOOGLE_CALENDAR_EVENTS_ENDPOINT (POST)."""
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
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

    def test_get_all_events_api_without_ldaps(self):
        """Test GOOGLE_CALENDAR_EVENTS_ENDPOINT (POST) without ldaps."""
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
        self.date_time_util.get_start_end_timestamps.return_value = (None, None)

        payload = {
            "calendarIds": ["cal1"],
            "startDate": "2023-01-01",
        }

        response = self.client.post(
            GOOGLE_CALENDAR_EVENTS_ENDPOINT,
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.google_calendar_analytics_service.get_all_events_from_calendars.assert_called_once_with(
            ["cal1"],
            [],
            None,
            None,
        )

    # Gerrit API tests

    def test_get_gerrit_stats(self):
        """Test GERRIT_STATS_ENDPOINT (POST)."""
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
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
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
        response = self.client.get(GERRIT_PROJECTS_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.gerrit_analytics_service.get_gerrit_projects.assert_called_once()

    # Google Chat API tests

    def test_get_google_chat_messages_count(self):
        """Test GOOGLE_CHAT_COUNT_ENDPOINT (POST)."""
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
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
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
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
        """Test SUMMARY_ENDPOINT (POST) with the activity-summary permission."""
        self._set_auth([Permission.DASHBOARD_ACTIVITY_SUMMARY_READ])
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

    def test_get_my_summary_success(self):
        """Test MY_SUMMARY_ENDPOINT (POST) returns 200 when LD flag is enabled."""
        self._set_auth([Permission.DASHBOARD_ACTIVITY_SUMMARY_READ])
        self.launchdarkly_service.is_view_personal_summary_enabled.return_value = True
        self.summary_service.get_my_summary.return_value = ActivitySummaryDto(
            ldap="test",
            chat_count=0,
            meeting_hours=0,
            cl_merged=0,
            loc_merged=0,
            jira_issue_done=0,
        )

        payload = {"startDate": "2025-01-01", "endDate": "2026-01-31"}

        response = self.client.post(
            f"{MY_SUMMARY_ENDPOINT}?sub=test&primary_email=test@u.circlecat.org",
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.summary_service.get_my_summary.assert_called_once()

    def test_get_my_summary_when_ld_flag_disabled(self):
        """Test MY_SUMMARY_ENDPOINT (POST) is blocked when LD flag is disabled."""
        self._set_auth([Permission.DASHBOARD_ACTIVITY_SUMMARY_READ])
        self.launchdarkly_service.is_view_personal_summary_enabled.return_value = False

        payload = {"startDate": "2025-01-01", "endDate": "2026-01-31"}

        with self.assertRaises(PermissionError) as exc_info:
            self.client.post(
                f"{MY_SUMMARY_ENDPOINT}?sub=test&primary_email=test@u.circlecat.org",
                json=payload,
                headers=self.headers,
            )

        self.assertEqual(
            str(exc_info.exception),
            "View personal summary feature is not yet available.",
        )
        self.summary_service.get_my_summary.assert_not_called()

    # Authorization enforcement tests

    def test_forbidden_access(self):
        """Verify that non-admin users are forbidden from accessing admin endpoints."""
        self._set_auth([])

        response = self.client.get(JIRA_PROJECTS_ENDPOINT, headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.jira_analytics_service.get_all_jira_projects.assert_not_called()


if __name__ == "__main__":
    unittest.main()
