from http import HTTPStatus
from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.common.fast_api_response_wrapper import api_response
from backend.common.constants import (
    MicrosoftAccountStatus,
    MicrosoftGroups,
    JiraIssueStatus,
)
from backend.common.user_role import UserRole
from backend.utils.permission_decorators import authenticate
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


class MicrosoftChatCountRequest(BaseModel):
    ldaps: list[str] | None = None
    startDate: str | None = None
    endDate: str | None = None


class GoogleCalendarEventsRequest(BaseModel):
    calendarIds: list[str]
    ldaps: list[str]
    startDate: str | None = None
    endDate: str | None = None


class JiraBriefRequest(BaseModel):
    statusList: list[JiraIssueStatus]
    ldaps: list[str] | None = None
    projectIds: list[str] | None = None
    startDate: str | None = None
    endDate: str | None = None


class JiraDetailBatchRequest(BaseModel):
    issueIds: list[str]


class GerritStatsRequest(BaseModel):
    ldaps: list[str] | None = None
    startDate: str | None = None
    endDate: str | None = None
    project: list[str] | None = None
    includeAllProjects: bool | None = False


class GoogleChatCountRequest(BaseModel):
    ldaps: list[str] | None = None
    spaceIds: list[str] | None = None
    startDate: str | None = None
    endDate: str | None = None


class SummaryRequest(BaseModel):
    startDate: str | None = None
    endDate: str | None = None
    groups: list[str]
    includeTerminated: bool | None = False


class FrontendController:
    def __init__(
        self,
        ldap_service,
        microsoft_chat_analytics_service,
        microsoft_meeting_chat_topic_cache_service,
        jira_analytics_service,
        google_calendar_analytics_service,
        google_chat_analytics_service,
        date_time_util,
        gerrit_analytics_service,
        summary_service,
    ):
        """
        Initialize the FrontendController with required dependencies.

        Args:
            ldap_service: LdapService instance.
            microsoft_chat_analytics_service: MicrosoftChatAnalyticsService instance.
            microsoft_meeting_chat_topic_cache_service: MicrosoftMeetingChatTopicCacheService instance.
            google_calendar_analytics_service: GoogleCalendarAnalyticsService instance.
            google_chat_analytics_service: GoogleChatAnalyticsService instance.
            date_time_util: DateTimeUtil instance.
            gerrit_analytics_service: GerritAnalyticsService instance.
        """
        self.ldap_service = ldap_service
        self.microsoft_chat_analytics_service = microsoft_chat_analytics_service
        self.microsoft_meeting_chat_topic_cache_service = (
            microsoft_meeting_chat_topic_cache_service
        )
        self.jira_analytics_service = jira_analytics_service
        self.google_calendar_analytics_service = google_calendar_analytics_service
        self.google_chat_analytics_service = google_chat_analytics_service
        self.date_time_util = date_time_util
        self.gerrit_analytics_service = gerrit_analytics_service
        self.summary_service = summary_service

        self.router = APIRouter(tags=["internal_activity"])

        self.router.add_api_route(
            MICROSOFT_LDAPS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.CC_INTERNAL])(
                self.get_ldaps_and_names
            ),
            methods=["GET"],
        )
        self.router.add_api_route(
            MICROSOFT_CHAT_COUNT_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.count_microsoft_chat_messages
            ),
            methods=["POST"],
        )
        self.router.add_api_route(
            MICROSOFT_CHAT_TOPICS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.all_microsoft_chat_topics
            ),
            methods=["GET"],
        )
        self.router.add_api_route(
            JIRA_PROJECTS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.get_all_jira_projects_api
            ),
            methods=["GET"],
        )
        self.router.add_api_route(
            GOOGLE_CALENDAR_LIST_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.get_all_calendars_api),
            methods=["GET"],
        )
        self.router.add_api_route(
            GOOGLE_CALENDAR_EVENTS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.get_all_events_api),
            methods=["POST"],
        )
        self.router.add_api_route(
            JIRA_BRIEF_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.get_jira_brief),
            methods=["POST"],
        )
        self.router.add_api_route(
            JIRA_DETAIL_BATCH_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.get_issue_detail_batch),
            methods=["POST"],
        )
        self.router.add_api_route(
            GERRIT_STATS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.get_gerrit_stats),
            methods=["POST"],
        )
        self.router.add_api_route(
            GERRIT_PROJECTS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.get_gerrit_projects),
            methods=["GET"],
        )
        self.router.add_api_route(
            GOOGLE_CHAT_COUNT_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.get_google_chat_messages_count
            ),
            methods=["POST"],
        )
        self.router.add_api_route(
            GOOGLE_CHAT_SPACES_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.get_chat_spaces_route),
            methods=["GET"],
        )
        self.router.add_api_route(
            SUMMARY_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.CC_INTERNAL])(self.get_summary),
            methods=["POST"],
        )

    async def get_chat_spaces_route(self, spaceType: str = "SPACE"):
        """API endpoint to retrieve chat spaces of a specified type."""
        spaces = self.google_chat_analytics_service.get_chat_spaces_by_type(spaceType)
        return api_response(
            success=True,
            message="Successfully.",
            data=spaces,
            status_code=HTTPStatus.OK,
        )

    async def get_google_chat_messages_count(self, body: GoogleChatCountRequest):
        """Count chat messages in Redis within a specified date range."""
        result = self.google_chat_analytics_service.count_messages(
            space_ids=body.spaceIds,
            sender_ldaps=body.ldaps,
            start_date=body.startDate,
            end_date=body.endDate,
        )
        return api_response(
            success=True,
            message="Successfully.",
            data=result,
            status_code=HTTPStatus.OK,
        )

    async def get_issue_detail_batch(self, body: JiraDetailBatchRequest):
        """Get Jira issue details in batch from Redis."""
        result = self.jira_analytics_service.process_get_issue_detail_batch(
            body.issueIds
        )
        return api_response(
            success=True,
            message="Successful",
            data=result,
            status_code=HTTPStatus.OK,
        )

    async def get_jira_brief(self, body: JiraBriefRequest):
        """Get Jira issue IDs in Redis by status."""
        result = self.jira_analytics_service.get_issues_summary(
            status_list=body.statusList,
            ldaps=body.ldaps,
            project_ids=body.projectIds,
            start_date=body.startDate,
            end_date=body.endDate,
        )
        return api_response(
            success=True,
            message="Successfully.",
            data=result,
            status_code=HTTPStatus.OK,
        )

    async def all_microsoft_chat_topics(self):
        """Fetch Microsoft chat topics from Redis."""
        response = await self.microsoft_meeting_chat_topic_cache_service.get_microsoft_chat_topics()
        return api_response(
            success=True,
            message="Successfully.",
            data=response,
            status_code=HTTPStatus.OK,
        )

    async def get_ldaps_and_names(
        self,
        status: MicrosoftAccountStatus,
        groups: list[MicrosoftGroups] = Query(
            ...,
            alias="groups[]",
            min_items=1,
        ),
    ):
        """Retrieve Microsoft 365 user LDAP information."""
        data = self.ldap_service.get_ldaps_by_status_and_group(
            status=status,
            groups=groups,
        )
        return api_response(
            success=True,
            message="Successfully.",
            data=data,
            status_code=HTTPStatus.OK,
        )

    async def count_microsoft_chat_messages(self, body: MicrosoftChatCountRequest):
        """Count Microsoft chat messages in Redis by sender."""
        response = self.microsoft_chat_analytics_service.count_microsoft_chat_messages_in_date_range(
            ldap_list=body.ldaps,
            start_date=body.startDate,
            end_date=body.endDate,
        )
        return api_response(
            success=True,
            message="Successfully.",
            data=response,
            status_code=HTTPStatus.OK,
        )

    async def get_all_jira_projects_api(self):
        """API endpoint to get a mapping of all project IDs to their names."""
        jira_data = self.jira_analytics_service.get_all_jira_projects()
        return api_response(
            success=True,
            message="Fetch jira projects successful",
            data=jira_data,
            status_code=HTTPStatus.OK,
        )

    async def get_all_calendars_api(self):
        """API endpoint to get Google Calendar list from Redis."""
        calendar_data = self.google_calendar_analytics_service.get_all_calendars()
        return api_response(
            success=True,
            message="Calendar list fetched successfully.",
            data=calendar_data,
            status_code=HTTPStatus.OK,
        )

    async def get_all_events_api(self, body: GoogleCalendarEventsRequest):
        """API endpoint to get Google Calendar events for users from Redis."""
        if not body.calendarIds:
            return api_response(
                success=False,
                message="Missing required query parameters: calendarIds.",
                status_code=HTTPStatus.BAD_REQUEST,
            )

        start_dt, end_dt = self.date_time_util.get_start_end_timestamps(
            body.startDate, body.endDate
        )

        calendar_data = (
            self.google_calendar_analytics_service.get_all_events_from_calendars(
                body.calendarIds,
                body.ldaps,
                start_dt,
                end_dt,
            )
        )
        return api_response(
            success=True,
            message="Calendar events fetched successfully.",
            data=calendar_data,
            status_code=HTTPStatus.OK,
        )

    async def get_gerrit_stats(self, body: GerritStatsRequest):
        """API endpoint to retrieve aggregated Gerrit stats."""
        response = self.gerrit_analytics_service.get_gerrit_stats(
            ldap_list=body.ldaps,
            start_date_str=body.startDate,
            end_date_str=body.endDate,
            project_list=body.project,
            include_full_stats=True,
            include_all_projects=body.includeAllProjects,
        )
        return api_response(
            success=True,
            message="Successfully.",
            data=response,
            status_code=HTTPStatus.OK,
        )

    async def get_gerrit_projects(self):
        """API endpoint to retrieve the list of Gerrit projects."""
        projects = self.gerrit_analytics_service.get_gerrit_projects()
        return api_response(
            success=True,
            message="Successfully retrieved Gerrit projects.",
            data=projects,
            status_code=HTTPStatus.OK,
        )

    async def get_summary(self, body: SummaryRequest):
        """API endpoint to retrieve the summary on the dashboard."""
        summary_data = self.summary_service.get_summary(
            body.startDate, body.endDate, body.groups, body.includeTerminated
        )
        return api_response(
            success=True,
            message="Summary fetched successfully",
            data=summary_data,
            status_code=HTTPStatus.OK,
        )
