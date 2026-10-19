import asyncio
from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase, TestCase, main
from unittest.mock import AsyncMock, Mock
from backend.internal_activity_service.activity_query_cache import (
    ActivityQueryCache,
)
from backend.internal_activity_service.summary_service import SummaryService
from backend.dto.user_context_dto import UserContextDto

SEPT_START = datetime(2025, 9, 1, tzinfo=timezone.utc)
SEPT_END = datetime(2025, 9, 30, 23, 59, 59, tzinfo=timezone.utc)


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
            user_emails_repository=Mock(),
            activity_query_cache=ActivityQueryCache(logger=Mock()),
        )

    def test_get_summary_single_user(self):
        ldap_user = "alice"

        self.mock_ldap_service.get_ldaps_by_status_and_group.return_value = {
            "interns": {"active": {ldap_user: "Alice Doe"}}
        }

        self.mock_date_time_util.get_start_end_timestamps.return_value = (
            SEPT_START,
            SEPT_END,
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
            SEPT_START,
            SEPT_END,
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
            SEPT_START,
            SEPT_END,
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
            SEPT_START,
            SEPT_END,
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

    def _stub_empty_analytics(self):
        self.mock_date_time_util.get_start_end_timestamps.return_value = (
            SEPT_START,
            SEPT_END,
        )
        self.mock_ms_chat_service.count_microsoft_chat_messages_in_date_range.return_value = {
            "result": {"alice": 1, "bob": 2}
        }
        self.mock_google_chat_service.count_messages.return_value = {"result": {}}
        self.mock_calendar_service.get_all_calendars.return_value = []
        self.mock_calendar_service.get_meeting_hours_for_user.return_value = {}
        self.mock_gerrit_service.get_gerrit_stats.return_value = {}
        self.mock_jira_service.get_issues_summary.return_value = {}

    def test_search_summary_data_repeated_query_is_computed_once(self):
        self._stub_empty_analytics()

        first = self.service._search_summary_data(
            ["alice", "bob"], "2025-09-01", "2025-09-30"
        )
        first[0]["chat_count"] = 999
        second = self.service._search_summary_data(
            ["alice", "bob"], "2025-09-01", "2025-09-30"
        )

        self.assertEqual(second[0]["chat_count"], 1)
        self.mock_ms_chat_service.count_microsoft_chat_messages_in_date_range.assert_called_once()
        self.mock_calendar_service.get_all_calendars.assert_called_once()

    def test_search_summary_data_keeps_rows_in_the_order_asked(self):
        self._stub_empty_analytics()

        self.service._search_summary_data(["alice", "bob"], None, None)
        second = self.service._search_summary_data(["bob", "alice"], None, None)

        self.assertEqual([row["ldap"] for row in second], ["bob", "alice"])

    def test_search_summary_data_different_range_is_computed_again(self):
        self._stub_empty_analytics()
        october_end = datetime(2025, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
        self.mock_date_time_util.get_start_end_timestamps.side_effect = [
            (SEPT_START, SEPT_END),
            (SEPT_START, october_end),
        ]

        self.service._search_summary_data(["alice"], "2025-09-01", "2025-09-30")
        self.service._search_summary_data(["alice"], "2025-09-01", "2025-10-31")

        self.assertEqual(
            self.mock_ms_chat_service.count_microsoft_chat_messages_in_date_range.call_count,
            2,
        )

    def test_my_summary_is_cached_by_ldap_not_by_user(self):
        self._stub_empty_analytics()
        self.service.user_emails_repository.list_by_user_id = AsyncMock(
            return_value=[Mock(email="alice@circlecat.org", otp_confirmed=True)]
        )
        first_account = UserContextDto(user_id=1, sub="a", primary_email="a@x.org")
        second_account = UserContextDto(user_id=2, sub="b", primary_email="b@x.org")

        first = asyncio.run(self.service.get_my_summary(Mock(), first_account))
        second = asyncio.run(self.service.get_my_summary(Mock(), second_account))

        self.assertEqual(first.ldap, "alice")
        self.assertEqual(second.chat_count, 1)
        self.mock_ms_chat_service.count_microsoft_chat_messages_in_date_range.assert_called_once()


def _email(address, confirmed=True):
    return Mock(email=address, otp_confirmed=confirmed)


class TestGetMySummary(IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = Mock()
        self.user_emails_repository = Mock()
        self.user_emails_repository.list_by_user_id = AsyncMock(return_value=[])
        self.service = SummaryService(
            ldap_service=Mock(),
            microsoft_chat_analytics_service=Mock(),
            google_calendar_analytics_service=Mock(),
            google_chat_analytics_service=Mock(),
            gerrit_analytics_service=Mock(),
            jira_analytics_service=Mock(),
            date_time_util=Mock(),
            user_emails_repository=self.user_emails_repository,
            activity_query_cache=ActivityQueryCache(logger=Mock()),
        )
        self.service._search_summary_data = Mock(return_value=[])

    async def _get(self, user):
        return await self.service.get_my_summary(
            self.session, user, start_date="2025-09-01", end_date="2025-09-30"
        )

    async def test_reads_the_ldap_off_the_confirmed_company_address(self):
        # Signed in with a personal address; the company address on the same
        # account is what names them in the activity data.
        self.user_emails_repository.list_by_user_id.return_value = [
            _email("alice.personal@gmail.com"),
            _email("alice@circlecat.org"),
        ]
        self.service._search_summary_data.return_value = [
            {
                "ldap": "alice",
                "chat_count": 10,
                "meeting_hours": 4.5,
                "cl_merged": 10,
                "loc_merged": 500,
                "jira_issue_done": 2,
            }
        ]
        user = UserContextDto(
            sub="s", primary_email="alice.personal@gmail.com", user_id=7
        )

        result = await self._get(user)

        self.user_emails_repository.list_by_user_id.assert_awaited_once_with(
            self.session, 7
        )
        self.service._search_summary_data.assert_called_once_with(
            ["alice"], "2025-09-01", "2025-09-30"
        )
        self.assertEqual(result.ldap, "alice")
        self.assertEqual(result.chat_count, 10)
        self.assertEqual(result.meeting_hours, 4.5)
        self.assertEqual(result.cl_merged, 10)
        self.assertEqual(result.loc_merged, 500)
        self.assertEqual(result.jira_issue_done, 2)

    async def test_zero_metrics_when_there_is_no_activity(self):
        self.user_emails_repository.list_by_user_id.return_value = [
            _email("alice@circlecat.org")
        ]
        user = UserContextDto(sub="s", primary_email="alice@circlecat.org", user_id=7)

        result = await self._get(user)

        self.assertEqual(result.ldap, "alice")
        self.assertEqual(result.chat_count, 0)
        self.assertEqual(result.meeting_hours, 0)
        self.assertEqual(result.cl_merged, 0)
        self.assertEqual(result.loc_merged, 0)
        self.assertEqual(result.jira_issue_done, 0)

    async def test_refuses_an_account_without_a_company_address(self):
        # The part before @ of an outside address can equal an employee's
        # ldap; reading it as one would show that employee's activity.
        self.user_emails_repository.list_by_user_id.return_value = [
            _email("alice@gmail.com")
        ]
        user = UserContextDto(sub="s", primary_email="alice@gmail.com", user_id=7)

        with self.assertRaises(PermissionError):
            await self._get(user)
        self.service._search_summary_data.assert_not_called()

    async def test_refuses_an_unconfirmed_company_address(self):
        # Anyone can add an address they do not own; only a confirmed one
        # proves it is theirs.
        self.user_emails_repository.list_by_user_id.return_value = [
            _email("mallory@gmail.com"),
            _email("alice@circlecat.org", confirmed=False),
        ]
        user = UserContextDto(sub="s", primary_email="mallory@gmail.com", user_id=7)

        with self.assertRaises(PermissionError):
            await self._get(user)
        self.service._search_summary_data.assert_not_called()

    async def test_refuses_a_user_with_no_account(self):
        user = UserContextDto(sub="s", primary_email="alice@circlecat.org")

        with self.assertRaises(PermissionError):
            await self._get(user)
        self.user_emails_repository.list_by_user_id.assert_not_called()
        self.service._search_summary_data.assert_not_called()


if __name__ == "__main__":
    main()
