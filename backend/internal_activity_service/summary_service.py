from backend.common.constants import MicrosoftAccountStatus, MicrosoftGroups
from backend.common.constants import JiraIssueStatus
from backend.dto.user_context_dto import UserContextDto
from backend.dto.internal_activity_summary_response_dto import ActivitySummaryDto


class SummaryService:
    def __init__(
        self,
        ldap_service,
        microsoft_chat_analytics_service,
        google_calendar_analytics_service,
        google_chat_analytics_service,
        gerrit_analytics_service,
        jira_analytics_service,
        date_time_util,
    ):
        """
        Initialize the SummaryService with required dependencies.

        Args:
            ldap_service: LdapService instance.
            microsoft_chat_analytics_service: MicrosoftChatAnalyticsService instance.
            google_calendar_analytics_service: GoogleCalendarAnalyticsService instance.
            google_chat_analytics_service: GoogleChatAnalyticsService instance.
            date_time_util: DateTimeUtil instance.
            gerrit_analytics_service: GerritAnalyticsService instance.
            date_time_util: DateTimeUtil instance.
        """
        self.ldap_service = ldap_service
        self.microsoft_chat_analytics_service = microsoft_chat_analytics_service
        self.google_calendar_analytics_service = google_calendar_analytics_service
        self.google_chat_analytics_service = google_chat_analytics_service
        self.gerrit_analytics_service = gerrit_analytics_service
        self.jira_analytics_service = jira_analytics_service
        self.date_time_util = date_time_util

    def _search_summary_data(self, ldaps: list[str], start_date, end_date) -> list:
        """Private method to fetch summary data for given LDAPs"""
        if not ldaps:
            return []

        start_dt, end_dt = self.date_time_util.get_start_end_timestamps(
            start_date, end_date
        )

        ms_chat_data = self.microsoft_chat_analytics_service.count_microsoft_chat_messages_in_date_range(
            ldap_list=ldaps,
            start_date=start_date,
            end_date=end_date,
        ).get("result", {})

        google_chat_data = self.google_chat_analytics_service.count_messages(
            sender_ldaps=ldaps,
            start_date=start_date,
            end_date=end_date,
        ).get("result", {})

        calendars = self.google_calendar_analytics_service.get_all_calendars()
        calendar_ids = [c["id"] for c in calendars]

        meeting_hours_data = (
            self.google_calendar_analytics_service.get_meeting_hours_for_user(
                calendar_ids=calendar_ids,
                ldap_list=ldaps,
                start_date=start_dt,
                end_date=end_dt,
            )
        )

        gerrit_stats = self.gerrit_analytics_service.get_gerrit_stats(
            ldap_list=ldaps,
            start_date_str=start_date,
            end_date_str=end_date,
        )

        jira_summary = self.jira_analytics_service.get_issues_summary(
            status_list=[JiraIssueStatus.DONE],
            ldaps=ldaps,
            project_ids=None,
            start_date=start_date,
            end_date=end_date,
        )

        summary_data = []
        for ldap_user in ldaps:
            ms_chat_count = ms_chat_data.get(ldap_user, 0)

            google_chat_spaces = google_chat_data.get(ldap_user, {})
            google_chat_count = (
                sum(google_chat_spaces.values())
                if isinstance(google_chat_spaces, dict)
                else 0
            )

            chat_count = ms_chat_count + google_chat_count

            meeting_hours = (
                meeting_hours_data.get(ldap_user, 0)
                if isinstance(meeting_hours_data, dict)
                else 0
            )

            stats_for_user = gerrit_stats.get(ldap_user, {})
            cl_merged = stats_for_user.get("cl_merged", 0)
            loc_merged = stats_for_user.get("loc_merged", 0)

            jira_done_issues = jira_summary.get(ldap_user, {}).get("done", [])
            jira_done_count = len(jira_done_issues)

            summary_data.append({
                "ldap": ldap_user,
                "chat_count": chat_count,
                "meeting_hours": meeting_hours,
                "cl_merged": cl_merged,
                "loc_merged": loc_merged,
                "jira_issue_done": jira_done_count,
            })

        return summary_data

    def _summary_mapper(self, summary_dict: dict) -> ActivitySummaryDto:
        """
        Map raw summary data (dict) to ActivitySummaryDto.

        This mapper is intentionally kept separate from _search_summary_data
        to avoid changing the existing summary API response format.
        """
        return ActivitySummaryDto(
            ldap=summary_dict.get("ldap", ""),
            chat_count=summary_dict.get("chat_count", 0),
            meeting_hours=summary_dict.get("meeting_hours", 0.0),
            cl_merged=summary_dict.get("cl_merged", 0),
            loc_merged=summary_dict.get("loc_merged", 0),
            jira_issue_done=summary_dict.get("jira_issue_done", 0),
        )

    def get_summary(self, start_date, end_date, groups_list, include_terminated):
        """
        Get summary data for a list of groups, optionally including terminated users.
        Delegates actual data aggregation to _search_summary_data.
        """
        status = (
            MicrosoftAccountStatus.ALL
            if include_terminated
            else MicrosoftAccountStatus.ACTIVE
        )

        ldap_mapping = self.ldap_service.get_ldaps_by_status_and_group(
            status=status,
            groups=[MicrosoftGroups(g) for g in groups_list],
        )

        user_ldaps = []
        for group_data in ldap_mapping.values():
            for status_data in group_data.values():
                user_ldaps.extend(status_data.keys())

        # Call private method to aggregate summary data
        return self._search_summary_data(user_ldaps, start_date, end_date)

    def get_my_summary(
        self, user: UserContextDto, start_date=None, end_date=None
    ) -> ActivitySummaryDto:
        """
        Get summary data for the current user based on their primary email.

        Args:
            user (UserContextDto): The current user's context.
            start_date (str | None): Optional start date.
            end_date (str | None): Optional end date.

        Returns:
            ActivitySummaryDto: Activity summary for the current user. Metrics default to zero when no activity data is found.
        """
        primary_email = getattr(user, "primary_email", None)
        if not primary_email:
            raise ValueError("primary_email is missing from the user context.")

        ldap = primary_email.split("@")[0]

        data = self._search_summary_data([ldap], start_date, end_date)

        if not data:
            return ActivitySummaryDto(ldap=ldap)

        return self._summary_mapper(data[0])
