from unittest import TestCase, main
from unittest.mock import Mock
from backend.frontend_service.summary_service import SummaryService


class TestSummaryService(TestCase):
    def setUp(self):
        self.mock_ldap_service = Mock()
        self.mock_ms_chat_service = Mock()
        self.mock_calendar_service = Mock()
        self.mock_google_chat_service = Mock()
        self.mock_gerrit_service = Mock()
        self.mock_jira_service = Mock()
        self.mock_date_time_util = Mock()

        self.service = SummaryService(
            ldap_service=self.mock_ldap_service,
            microsoft_chat_analytics_service=self.mock_ms_chat_service,
            google_calendar_analytics_service=self.mock_calendar_service,
            google_chat_analytics_service=self.mock_google_chat_service,
            gerrit_analytics_service=self.mock_gerrit_service,
            jira_analytics_service=self.mock_jira_service,
            date_time_util=self.mock_date_time_util,
        )

    def test_get_summary_single_user(self):
        ldap_user = "alice"

        self.mock_ldap_service.get_ldaps_by_status_and_group.return_value = {
            "interns": {"active": {ldap_user: "Alice Doe"}}
        }

        self.mock_date_time_util.get_start_end_timestamps.return_value = (
            "2025-09-01T00:00:00",
            "2025-09-30T23:59:59",
        )

        self.mock_ms_chat_service.count_microsoft_chat_messages_in_date_range.return_value = {
            "result": {ldap_user: 5}
        }

        self.mock_google_chat_service.count_messages.return_value = {
            "result": {ldap_user: {"space1": 3, "space2": 2}}
        }

        self.mock_calendar_service.get_all_calendars.return_value = [
            {"id": "cal1", "name": "Calendar 1"}
        ]
        self.mock_calendar_service.get_meeting_hours_for_user.return_value = {
            ldap_user: 4.5
        }

        self.mock_gerrit_service.get_gerrit_stats.return_value = {
            ldap_user: {"cl_merged": 10, "loc_merged": 500}
        }

        self.mock_jira_service.get_issues_summary.return_value = {
            ldap_user: {"done": ["JIRA-1", "JIRA-2"]}
        }

        result = self.service.get_summary(
            start_date="2025-09-01",
            end_date="2025-09-30",
            groups_list=["interns"],
            include_terminated=False,
        )

        expected = [
            {
                "ldap": ldap_user,
                "chat_count": 10,
                "meeting_hours": 4.5,
                "cl_merged": 10,
                "loc_merged": 500,
                "jira_issue_done": 2,
            }
        ]
        self.assertEqual(result, expected)

        self.mock_ms_chat_service.count_microsoft_chat_messages_in_date_range.assert_called_once_with(
            ldap_list=[ldap_user],
            start_date="2025-09-01",
            end_date="2025-09-30",
        )

        self.mock_google_chat_service.count_messages.assert_called_once_with(
            sender_ldaps=[ldap_user],
            start_date="2025-09-01",
            end_date="2025-09-30",
        )

        self.mock_calendar_service.get_meeting_hours_for_user.assert_called_once()
        self.mock_gerrit_service.get_gerrit_stats.assert_called_once()
        self.mock_jira_service.get_issues_summary.assert_called_once()

    def test_get_summary_multiple_users(self):
        self.mock_ldap_service.get_ldaps_by_status_and_group.return_value = {
            "interns": {"active": {"alice": "Alice Doe"}},
            "employees": {"active": {"bob": "Bob Smith"}},
        }

        self.mock_date_time_util.get_start_end_timestamps.return_value = (
            "2025-09-01T00:00:00",
            "2025-09-30T23:59:59",
        )

        self.mock_ms_chat_service.count_microsoft_chat_messages_in_date_range.return_value = {
            "result": {"alice": 5, "bob": 7}
        }

        self.mock_google_chat_service.count_messages.return_value = {
            "result": {"alice": {"space1": 3}, "bob": {"space2": 2, "space3": 1}}
        }

        self.mock_calendar_service.get_all_calendars.return_value = [
            {"id": "cal1", "name": "Calendar 1"}
        ]
        self.mock_calendar_service.get_meeting_hours_for_user.return_value = {
            "alice": 4.5,
            "bob": 6,
        }

        self.mock_gerrit_service.get_gerrit_stats.return_value = {
            "alice": {"cl_merged": 10, "loc_merged": 500},
            "bob": {"cl_merged": 5, "loc_merged": 250},
        }

        self.mock_jira_service.get_issues_summary.return_value = {
            "alice": {"done": ["JIRA-1"]},
            "bob": {"done": ["JIRA-2", "JIRA-3"]},
        }

        result = self.service.get_summary(
            start_date="2025-09-01",
            end_date="2025-09-30",
            groups_list=["interns", "employees"],
            include_terminated=False,
        )

        expected = [
            {
                "ldap": "alice",
                "chat_count": 8,
                "meeting_hours": 4.5,
                "cl_merged": 10,
                "loc_merged": 500,
                "jira_issue_done": 1,
            },
            {
                "ldap": "bob",
                "chat_count": 10,
                "meeting_hours": 6,
                "cl_merged": 5,
                "loc_merged": 250,
                "jira_issue_done": 2,
            },
        ]

        self.assertEqual(result, expected)

    def test_get_summary_no_users(self):
        self.mock_ldap_service.get_ldaps_by_status_and_group.return_value = {}
        self.mock_calendar_service.get_all_calendars.return_value = []
        self.mock_date_time_util.get_start_end_timestamps.return_value = (
            "start",
            "end",
        )

        result = self.service.get_summary(
            start_date="2025-09-01",
            end_date="2025-09-30",
            groups_list=["interns"],
            include_terminated=False,
        )

        self.assertEqual(result, [])

    def test_get_summary_empty_analytics(self):
        users = ["alice"]
        self.mock_ldap_service.get_ldaps_by_status_and_group.return_value = {
            "interns": {"active": {user: "Alice Doe" for user in users}}
        }
        self.mock_date_time_util.get_start_end_timestamps.return_value = (
            "start",
            "end",
        )
        self.mock_ms_chat_service.count_microsoft_chat_messages_in_date_range.return_value = {
            "result": {}
        }
        self.mock_google_chat_service.count_messages.return_value = {"result": {}}
        self.mock_calendar_service.get_all_calendars.return_value = [{"id": "cal1"}]
        self.mock_calendar_service.get_meeting_hours_for_user.return_value = {}
        self.mock_gerrit_service.get_gerrit_stats.return_value = {}
        self.mock_jira_service.get_issues_summary.return_value = {}

        result = self.service.get_summary(
            start_date="start",
            end_date="end",
            groups_list=["interns"],
            include_terminated=True,
        )

        expected = [
            {
                "ldap": "alice",
                "chat_count": 0,
                "meeting_hours": 0,
                "cl_merged": 0,
                "loc_merged": 0,
                "jira_issue_done": 0,
            }
        ]
        self.assertEqual(result, expected)


if __name__ == "__main__":
    main()
