import unittest
from datetime import datetime, timezone
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
from backend.common.exceptions import ActivityDataUnavailableError
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.utils.auth_middleware import AuthMiddleware
from backend.internal_activity_service.internal_activity_controller import (
    InternalActivityController,
)
from backend.dto.internal_activity_summary_response_dto import ActivitySummaryDto
from backend.internal_activity_service.activity_query_cache import (
    ActivityQueryCache,
)
from backend.internal_activity_service.gerrit_analytics_service import (
    GerritAnalyticsService,
)
from backend.internal_activity_service.ldap_service import LdapService
from backend.internal_activity_service.summary_service import SummaryService


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

        self.mock_session = MagicMock()
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=self.mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        begin_cm = MagicMock()
        begin_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        begin_cm.__aexit__ = AsyncMock(return_value=False)
        self.mock_session.begin = MagicMock(return_value=begin_cm)
        self.mock_database = MagicMock()
        self.mock_database.session = MagicMock(return_value=session_cm)

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
            database=self.mock_database,
        )

        self.mock_user_identity_service = MagicMock()
        self.mock_user_identity_service.find_user_by_sub = AsyncMock(
            return_value=MagicMock(
                user_id=1,
                is_super_admin=False,
                is_active=True,
                is_blocked=False,
            )
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
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
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

    def test_get_summary_refuses_an_empty_group_list(self):
        """No group means no members to sum; it used to reach the LDAP lookup
        and fail there with a 500. The app maps this validation error to 400;
        this bare test app leaves FastAPI's 422."""
        self._set_auth([Permission.DASHBOARD_ACTIVITY_SUMMARY_READ])

        response = self.client.post(
            SUMMARY_ENDPOINT,
            json={"startDate": "2023-01-01", "groups": []},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.summary_service.get_summary.assert_not_called()

    def test_get_my_summary_success(self):
        """Test MY_SUMMARY_ENDPOINT (POST) returns 200 when LD flag is enabled."""
        self._set_auth([Permission.DASHBOARD_ACTIVITY_SUMMARY_READ])
        self.launchdarkly_service.is_view_personal_summary_enabled.return_value = True
        self.summary_service.get_my_summary = AsyncMock()
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
        self.summary_service.get_my_summary.assert_awaited_once()
        self.assertIs(
            self.summary_service.get_my_summary.await_args.args[0], self.mock_session
        )

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

    def _client_with_exception_handlers(self):
        register_exception_handlers(self.app)
        return TestClient(self.app, raise_server_exceptions=False)

    def test_get_summary_returns_503_when_redis_answers_short(self):
        self._set_auth([Permission.DASHBOARD_ACTIVITY_SUMMARY_READ])
        self.summary_service.get_summary.side_effect = ActivityDataUnavailableError(
            "Redis pipeline returned 1 results for 2 commands."
        )
        client = self._client_with_exception_handlers()

        response = client.post(
            SUMMARY_ENDPOINT,
            json={"startDate": "2023-01-01", "groups": ["employees"]},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.json()["message"], "Activity data is temporarily unavailable."
        )

    def test_get_gerrit_stats_returns_503_when_redis_answers_short(self):
        self._set_auth([Permission.INTERNAL_ACTIVITY_READ])
        self.gerrit_analytics_service.get_gerrit_stats.side_effect = (
            ActivityDataUnavailableError("short")
        )
        client = self._client_with_exception_handlers()

        response = client.post(
            GERRIT_STATS_ENDPOINT, json={"ldaps": ["a"]}, headers=self.headers
        )

        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.json()["message"], "Activity data is temporarily unavailable."
        )

    def _wire_real_ldap_read_failing_with(self, reply):
        """Real ldap, Gerrit and summary services over a Redis whose pipelines
        all answer ``reply``."""
        redis_client = MagicMock()
        redis_client.pipeline.return_value.execute.return_value = reply
        retry_utils = MagicMock()
        retry_utils.get_retry_on_transient.side_effect = lambda fn, *args, **kwargs: fn(
            *args, **kwargs
        )
        date_time_util = MagicMock()
        date_time_util.get_start_end_timestamps.return_value = (
            datetime(2025, 10, 21, tzinfo=timezone.utc),
            datetime(2025, 10, 28, tzinfo=timezone.utc),
        )
        cache = ActivityQueryCache(logger=MagicMock())
        ldap_service = LdapService(
            logger=MagicMock(), redis_client=redis_client, retry_utils=retry_utils
        )
        self.controller.gerrit_analytics_service = GerritAnalyticsService(
            logger=MagicMock(),
            redis_client=redis_client,
            retry_utils=retry_utils,
            ldap_service=ldap_service,
            date_time_util=date_time_util,
            gerrit_client=MagicMock(),
            activity_query_cache=cache,
        )
        self.controller.summary_service = SummaryService(
            ldap_service=ldap_service,
            microsoft_chat_analytics_service=MagicMock(),
            google_calendar_analytics_service=MagicMock(),
            google_chat_analytics_service=MagicMock(),
            gerrit_analytics_service=self.controller.gerrit_analytics_service,
            jira_analytics_service=MagicMock(),
            date_time_util=date_time_util,
            user_emails_repository=MagicMock(),
            activity_query_cache=cache,
        )
        return cache

    def test_failed_ldap_read_answers_503_and_caches_nothing(self):
        # An empty reply is what a retried pipeline gives back after a Redis
        # error; before, it read as "nobody" and the empty result was cached.
        self._set_auth([
            Permission.INTERNAL_ACTIVITY_READ,
            Permission.DASHBOARD_ACTIVITY_SUMMARY_READ,
        ])
        requests = {
            "gerrit stats": (GERRIT_STATS_ENDPOINT, {}),
            "summary": (
                SUMMARY_ENDPOINT,
                {"startDate": "2025-10-21", "groups": ["employees"]},
            ),
        }
        for name, (url, body) in requests.items():
            for reply in ([], [Exception("connection reset")]):
                with self.subTest(request=name, reply=reply):
                    cache = self._wire_real_ldap_read_failing_with(reply)
                    client = self._client_with_exception_handlers()

                    response = client.post(url, json=body, headers=self.headers)

                    self.assertEqual(
                        response.status_code, HTTPStatus.SERVICE_UNAVAILABLE
                    )
                    self.assertEqual(len(cache), 0)


if __name__ == "__main__":
    unittest.main()
