import json
from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import MagicMock, AsyncMock
from flask import Flask
from backend.frontend_service.frontend_controller import (
    FrontendController,
    MicrosoftAccountStatus,
    MicrosoftGroups,
)
from datetime import datetime, timezone

MICROSOFT_LDAP_FETCHER_API = "/api/microsoft/{status}/ldaps"
GOOGLE_CHAT_COUNT_API = "/api/google/chat/count"
JIRA_BRIEF_API = "/api/jira/brief"
GOOGLE_CALENDAR_CALENDARS_API = "/api/google/calendar/calendars"
JIRA_ISSUE_DETAIL_BATCH_API = "/api/jira/detail/batch"
GOOGLE_CALENDAR_EVENTS_API = "/api/google/calendar/events"
JIRA_PROJECT_API = "/api/jira/projects"
GERRIT_STATS_API = "/api/gerrit/stats"
GERRIT_PROJECTS_API = "/api/gerrit/projects"


class TestFrontendController(TestCase):
    def setUp(self):
        self.ldap_service = MagicMock()
        self.microsoft_chat_analytics_service = MagicMock()
        self.microsoft_meeting_chat_topic_cache_service = AsyncMock()
        self.mock_jira_analytics_service = MagicMock()
        self.google_calendar_analytics_service = MagicMock()
        self.date_time_util = MagicMock()
        self.mock_gerrit_analytics_service = MagicMock()
        self.mock_google_chat_analytics_service = MagicMock()
        self.controller = FrontendController(
            ldap_service=self.ldap_service,
            microsoft_chat_analytics_service=self.microsoft_chat_analytics_service,
            microsoft_meeting_chat_topic_cache_service=self.microsoft_meeting_chat_topic_cache_service,
            jira_analytics_service=self.mock_jira_analytics_service,
            google_calendar_analytics_service=self.google_calendar_analytics_service,
            date_time_util=self.date_time_util,
            gerrit_analytics_service=self.mock_gerrit_analytics_service,
            google_chat_analytics_service=self.mock_google_chat_analytics_service,
        )

        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

    async def asyncTearDown(self):
        self.app_context.pop()

    def test_get_chat_spaces_route(self):
        mock_data = [{"space id": "space name"}]
        self.mock_google_chat_analytics_service.get_chat_spaces_by_type.return_value = (
            mock_data
        )

        with self.app.test_request_context("/api/google/chat/spaces?spaceType=SPACE"):
            response = self.controller.get_chat_spaces_route()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_data)

        self.mock_google_chat_analytics_service.get_chat_spaces_by_type.assert_called_once()

    def test_get_google_chat_messages_count(self):
        mock_result = {}
        self.mock_google_chat_analytics_service.count_messages.return_value = (
            mock_result
        )

        with self.app.test_request_context(
            GOOGLE_CHAT_COUNT_API,
            method="POST",
            json={
                "startDate": "2025-01-01",
                "endDate": "2025-02-01",
                "spaceIds": ["space1"],
                "senderLdaps": ["ldap1"],
            },
        ):
            response = self.controller.get_google_chat_messages_count()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)
        self.mock_google_chat_analytics_service.count_messages.assert_called_once()

    def test_get_issue_detail_batch(self):
        mock_result = {}
        self.mock_jira_analytics_service.process_get_issue_detail_batch.return_value = (
            mock_result
        )

        with self.app.test_request_context(
            JIRA_BRIEF_API,
            method="POST",
            json={
                "issueIds": ["id1", "id2"],
            },
        ):
            response = self.controller.get_issue_detail_batch()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)
        self.mock_jira_analytics_service.process_get_issue_detail_batch.assert_called_once()

    def test_get_jira_brief(self):
        mock_result = {}
        self.mock_jira_analytics_service.get_issues_summary.return_value = mock_result

        with self.app.test_request_context(
            JIRA_BRIEF_API,
            method="POST",
            json={
                "statusList": ["done"],
                "ldaps": ["user1"],
                "projectIds": ["proj1"],
                "startDate": "2023-01-01",
                "endDate": "2023-01-31",
            },
        ):
            response = self.controller.get_jira_brief()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)
        self.mock_jira_analytics_service.get_issues_summary.assert_called_once()

    def test_get_ldaps_and_names_success_with_groups(self):
        mock_data = {"active": ["ldap1", "ldap2"]}
        self.ldap_service.get_ldaps_by_status_and_group.return_value = mock_data

        with self.app.test_request_context(
            "/microsoft/active/ldaps?groups[]=interns&groups[]=employees"
        ):
            response = self.controller.get_ldaps_and_names("active")

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertEqual(response.json["data"], mock_data)

            self.ldap_service.get_ldaps_by_status_and_group.assert_called_with(
                status=MicrosoftAccountStatus.ACTIVE,
                groups=[MicrosoftGroups.INTERNS, MicrosoftGroups.EMPLOYEES],
            )

    def test_get_ldaps_and_names_success_no_groups(self):
        mock_data = {"all": ["ldap1", "ldap2", "ldap3"]}
        self.ldap_service.get_ldaps_by_status_and_group.return_value = mock_data

        with self.app.test_request_context("/microsoft/all/ldaps"):
            response = self.controller.get_ldaps_and_names("all")

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertEqual(response.json["data"], mock_data)

            self.ldap_service.get_ldaps_by_status_and_group.assert_called_with(
                status=MicrosoftAccountStatus.ALL, groups=[]
            )

    def test_get_ldaps_and_names_invalid_status(self):
        with self.app.test_request_context("/microsoft/invalid/ldaps"):
            with self.assertRaises(ValueError):
                self.controller.get_ldaps_and_names("invalid")

    def test_count_microsoft_chat_messages_with_params(self):
        payload = {
            "ldaps": ["user1", "user2"],
            "startDate": "2024-01-01",
            "endDate": "2024-01-31",
        }
        mock_service_response = {
            "start_date": "2024-01-01T00:00:00+00:00",
            "end_date": "2024-01-31T23:59:59.999999+00:00",
            "result": {"user1": 10, "user2": 15},
        }
        self.microsoft_chat_analytics_service.count_microsoft_chat_messages_in_date_range.return_value = mock_service_response

        with self.app.test_request_context(
            "/api/microsoft/chat/count",
            method="POST",
            data=json.dumps(payload),
            content_type="application/json",
        ):
            response = self.controller.count_microsoft_chat_messages()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_service_response)

        self.microsoft_chat_analytics_service.count_microsoft_chat_messages_in_date_range.assert_called_once_with(
            ldap_list=["user1", "user2"],
            start_date="2024-01-01",
            end_date="2024-01-31",
        )

    def test_count_microsoft_chat_messages_no_params(self):
        payload = {}
        mock_service_response = {
            "start_date": "2024-01-01T00:00:00+00:00",
            "end_date": "2024-01-31T23:59:59.999999+00:00",
            "result": {"user1": 10, "user2": 15},
        }
        self.microsoft_chat_analytics_service.count_microsoft_chat_messages_in_date_range.return_value = mock_service_response

        with self.app.test_request_context(
            "/api/microsoft/chat/count",
            method="POST",
            data=json.dumps(payload),
            content_type="application/json",
        ):
            response = self.controller.count_microsoft_chat_messages()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_service_response)

        self.microsoft_chat_analytics_service.count_microsoft_chat_messages_in_date_range.assert_called_once_with(
            ldap_list=None,
            start_date=None,
            end_date=None,
        )

    async def test_all_microsoft_chat_topics(self):
        mock_data = {"id": "name"}
        self.microsoft_meeting_chat_topic_cache_service.get_microsoft_chat_topics().return_value = mock_data

        with self.app.test_request_context("/microsoft/chat/topics"):
            response = await self.controller.all_microsoft_chat_topics()

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertEqual(response.json["data"], mock_data)

            self.microsoft_meeting_chat_topic_cache_service.get_microsoft_chat_topics.assert_called_once()

    def test_get_all_jira_projects_success(self):
        mock_result = {"10503": "Intern Practice", "24998": "Purrf"}
        self.mock_jira_analytics_service.get_all_jira_projects.return_value = (
            mock_result
        )

        with self.app.test_request_context(JIRA_PROJECT_API):
            response = self.controller.get_all_jira_projects_api()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)
        self.assertIn("Fetch jira project", response.json["message"])
        self.mock_jira_analytics_service.get_all_jira_projects.assert_called_once()

    def test_get_google_calendar_calendars_success(self):
        mock_calendars = [
            {"id": "calendar1", "summary": "Team Calendar"},
            {"id": "calendar2", "summary": "Project Calendar"},
        ]
        self.google_calendar_analytics_service.get_all_calendars.return_value = (
            mock_calendars
        )

        with self.app.test_request_context("/calendar/calendars"):
            response = self.controller.get_all_calendars_api()

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertEqual(response.json["data"], mock_calendars)
            self.google_calendar_analytics_service.get_all_calendars.assert_called_once()

    def test_get_all_events_success(self):
        mock_events = {
            "ldap1": [{"event": "Meeting", "start": "2025-08-01T10:00:00Z"}],
            "ldap2": [{"event": "Workshop", "start": "2025-08-01T12:00:00Z"}],
        }
        self.google_calendar_analytics_service.get_all_events_from_calendars.return_value = mock_events
        self.date_time_util.get_start_end_timestamps.return_value = (
            datetime(2025, 8, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 8, 2, 0, 0, tzinfo=timezone.utc),
        )

        with self.app.test_request_context(
            "/calendar/events",
            method="POST",
            json={
                "calendarIds": ["cal1"],
                "ldaps": ["ldap1", "ldap2"],
                "startDate": "2025-08-01T00:00:00Z",
                "endDate": "2025-08-02T00:00:00Z",
            },
        ):
            response = self.controller.get_all_events_api()

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertEqual(response.json["data"], mock_events)
            self.google_calendar_analytics_service.get_all_events_from_calendars.assert_called_with(
                ["cal1"],
                ["ldap1", "ldap2"],
                datetime(2025, 8, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 8, 2, 0, 0, tzinfo=timezone.utc),
            )

    def test_get_all_events_api_success_no_ldaps(self):
        mock_events = {"ldap1": [{"event": "Meeting"}]}
        self.google_calendar_analytics_service.get_all_events_from_calendars.return_value = mock_events
        self.date_time_util.get_start_end_timestamps.return_value = (
            datetime(2025, 8, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 8, 2, 0, 0, tzinfo=timezone.utc),
        )

        with self.app.test_request_context(
            "/calendar/events",
            method="POST",
            json={
                "calendarIds": ["cal1"],
                "startDate": "2025-08-01T00:00:00Z",
                "endDate": "2025-08-02T00:00:00Z",
            },
        ):
            response = self.controller.get_all_events_api()

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertEqual(response.json["data"], mock_events)
            self.google_calendar_analytics_service.get_all_events_from_calendars.assert_called_with(
                ["cal1"],
                [],
                datetime(2025, 8, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 8, 2, 0, 0, tzinfo=timezone.utc),
            )

    def test_get_all_events_api_missing_required_params(self):
        with self.app.test_request_context("/calendar/events"):
            response = self.controller.get_all_events_api()

            self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
            self.assertIn("Missing required query parameters", response.json["message"])

    async def test_get_gerrit_stats_success(self):
        mock_stats = {
            "user1": {
                "cl_merged": 10,
                "cl_abandoned": 2,
                "cl_under_review": 1,
                "loc_merged": 150,
                "cl_reviewed": 5,
            }
        }
        self.mock_gerrit_analytics_service.get_gerrit_stats.return_value = mock_stats

        with self.app.test_request_context(
            GERRIT_STATS_API
            + "?ldap=user1&start_date_str=2024-01-01&end_date_str=2024-01-31&project=test_project",
            method="GET",
        ):
            response = await self.controller.get_gerrit_stats()

        self.mock_gerrit_analytics_service.get_gerrit_stats.assert_called_once_with(
            raw_ldap="user1",
            start_date_str="2024-01-01",
            end_date_str="2024-01-31",
            raw_project="test_project",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.get_json(),
            {"success": True, "message": "Successfully.", "data": mock_stats},
        )

    def test_get_gerrit_projects_success(self):
        mock_projects = ["proj1", "proj2"]
        self.mock_gerrit_analytics_service.get_gerrit_projects.return_value = (
            mock_projects
        )

        with self.app.test_request_context(GERRIT_PROJECTS_API, method="GET"):
            response = self.controller.get_gerrit_projects()

        self.mock_gerrit_analytics_service.get_gerrit_projects.assert_called_once()
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.get_json()["message"], "Successfully retrieved Gerrit projects."
        )
        self.assertEqual(response.get_json()["data"], mock_projects)


if __name__ == "__main__":
    main()
