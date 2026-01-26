from backend.common.constants import MicrosoftAccountStatus, MicrosoftGroups
from backend.common.constants import JiraIssueStatus


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
