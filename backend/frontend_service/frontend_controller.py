from flask import Blueprint, request
from http import HTTPStatus
from backend.common.constants import (
    MicrosoftAccountStatus,
    MicrosoftGroups,
    JiraIssueStatus,
)
from backend.common.api_response_wrapper import api_response


frontend_bp = Blueprint("frontend", __name__, url_prefix="/api")


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

    def register_routes(self, blueprint):
        """
        Register the routes on the given Flask blueprint.

        Args:
            blueprint: Flask Blueprint object to register routes on.
        """
        blueprint.add_url_rule(
            "/microsoft/<status>/ldaps",
            view_func=self.get_ldaps_and_names,
            methods=["GET"],
        )
        blueprint.add_url_rule(
            "/microsoft/chat/count",
            view_func=self.count_microsoft_chat_messages,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/microsoft/chat/topics",
            view_func=self.all_microsoft_chat_topics,
            methods=["GET"],
        )
        blueprint.add_url_rule(
            "/jira/projects",
            view_func=self.get_all_jira_projects_api,
            methods=["GET"],
        )
        blueprint.add_url_rule(
            "/calendar/calendars",
            view_func=self.get_all_calendars_api,
            methods=["GET"],
        )
        blueprint.add_url_rule(
            "/calendar/events",
            view_func=self.get_all_events_api,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/jira/brief",
            view_func=self.get_jira_brief,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/jira/detail/batch",
            view_func=self.get_issue_detail_batch,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/gerrit/stats",
            view_func=self.get_gerrit_stats,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/gerrit/projects",
            view_func=self.get_gerrit_projects,
            methods=["GET"],
        )

        blueprint.add_url_rule(
            "/google/chat/count",
            view_func=self.get_google_chat_messages_count,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/google/chat/spaces",
            view_func=self.get_chat_spaces_route,
            methods=["GET"],
        )

    def get_chat_spaces_route(self):
        """API endpoint to retrieve chat spaces of a specified type, default SPACE type."""
        space_type = request.args.get("spaceType", "SPACE")

        spaces = self.google_chat_analytics_service.get_chat_spaces_by_type(space_type)
        return api_response(
            success=True,
            message="Successfully.",
            data=spaces,
            status_code=HTTPStatus.OK,
        )

    def get_google_chat_messages_count(self):
        """
        Count chat messages in Redis within a specified date range.

        JSON Body Parameters:
            ldaps (list[str], optional): List of sender LDAPs.
            spaceIds (list[str], optional): List of space IDs.
            startDate (str, optional): Start date in "YYYY-MM-DD" format.
            endDate (str, optional): End date in "YYYY-MM-DD" format.

        Returns:
            Response (JSON): Message counts grouped by sender and space. Example:
            {
                "alice": {
                    "space1": 25,
                    "space2": 5
                },
                "bob": {
                    "space1": 11,
                    "space2": 0
                }
            }
        """
        data = request.get_json(force=True)
        sender_ldaps = data.get("ldaps")
        space_ids = data.get("spaceIds")
        start_date = data.get("startDate")
        end_date = data.get("endDate")

        result = self.google_chat_analytics_service.count_messages(
            space_ids=space_ids,
            sender_ldaps=sender_ldaps,
            start_date=start_date,
            end_date=end_date,
        )

        return api_response(
            success=True,
            message="Successfully.",
            data=result,
            status_code=HTTPStatus.OK,
        )

    def get_issue_detail_batch(self):
        """
        Get Jira issue details in batch from Redis.

        Fetch the full metadata of multiple Jira issues from Redis, given a list
        of issueIds.

        Request Body (JSON):
            { "issueIds": ["issue-1", "issue-2", ...] }

        Returns:
            JSON response with success flag, message, and data containing issue
            details.

            [
                {"issue_id": "issue-1", "field1": "value1", "field2": "value2"},
                {"issue_id": "issue-2", "field1": "value1", "field2": "value2"},
                {"issue_id": "issue-3", "field1": None, "field2": None}
            ]
        """
        data = request.get_json(force=True)
        issue_ids = data.get("issueIds") if data else None

        result = self.jira_analytics_service.process_get_issue_detail_batch(issue_ids)

        return api_response(
            success=True,
            message="Successful",
            data=result,
            status_code=HTTPStatus.OK,
        )

    def get_jira_brief(self):
        """
        Get Jira issue IDs in Redis by status: done, in_progress, todo, and all.

        Request body (JSON):
            {
                "statusList": ["done", "in_progress", "todo"],    list of statuses
                "ldaps": ["<ldap1>", "<ldap2>", ...],              list of users ldap
                "projectIds": ["<project1>", "<project2>", ...],  list of projects
                "startDate": "<yyyy-mm-dd>",
                "endDate": "<yyyy-mm-dd>"
            }

        Returns:
            Response (JSON): Standard API response with issue IDs grouped by status, ldap

            {
            "time_range": {
                "start_dt": "2023-01-01T00:00:00+00:00",
                "end_dt": "2023-01-31T23:59:59+00:00"
            },
            "user1": {
                "done": ["done-issue-1", "done-issue-2"],
                "in_progress": ["inprogress-issue-1"],
                "todo": [],
                "done_story_points_total": 8.0
            },
            "user2": {
                "done": [],
                "in_progress": ["inprogress-issue-2"],
                "todo": ["todo-issue-1"],
                "done_story_points_total": 0.0
            }
        }
        """
        data = request.get_json(force=True)
        status_list_str = data.get("statusList")
        status_list = [JiraIssueStatus(status_str) for status_str in status_list_str]
        ldaps = data.get("ldaps")
        project_ids = data.get("projectIds")
        start_date = data.get("startDate")
        end_date = data.get("endDate")

        result = self.jira_analytics_service.get_issues_summary(
            status_list=status_list,
            ldaps=ldaps,
            project_ids=project_ids,
            start_date=start_date,
            end_date=end_date,
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

    def get_ldaps_and_names(self, status):
        """
        API endpoint to retrieve Microsoft 365 user LDAP information from Redis, filtered by account status
        and optionally by multiple Microsoft groups.

        This endpoint expects the `groups[]` query parameter as a list (e.g., ?groups[]=interns&groups[]=employees).

        Args:
            status (str): The account status to filter by (e.g., "active", "terminated", "all").
                          Will be validated and converted to a MicrosoftAccountStatus enum.

        Returns:
            Response: JSON response containing the LDAP data organized by group and status, with HTTP status code 200.

        Example request:
            GET /microsoft/all/ldaps?groups[]=interns&groups[]=employees
        """
        groups_list = request.args.getlist("groups[]")
        data = self.ldap_service.get_ldaps_by_status_and_group(
            status=MicrosoftAccountStatus.validate_status(status),
            groups=[MicrosoftGroups(g) for g in groups_list],
        )

        return api_response(
            success=True,
            message="Successfully.",
            data=data,
            status_code=HTTPStatus.OK,
        )

    def count_microsoft_chat_messages(self):
        """
        Count Microsoft chat messages in Redis within a specified date range by sender.

        Request Body (JSON):
            {
                "ldaps": ["alice", "bob"],       # optional, list of user ldaps
                "startDate": "2024-06-01",     # optional
                "endDate": "2024-06-28"        # optional
            }

        Returns:
            Response (JSON): Message counts grouped by sender. Example:
            {
                "message": "Successfully.",
                "data": {
                            "start_date": "2024-06-01T00:00:00+00:00",
                            "end_date": "2024-06-28T23:59:59.999999+00:00",
                            "result": {
                                "alice": 25,
                                "bob": 11
                            }
                    }
            }
        """
        data = request.get_json(force=True)
        ldap_list = data.get("ldaps")
        start_date = data.get("startDate")
        end_date = data.get("endDate")

        response = self.microsoft_chat_analytics_service.count_microsoft_chat_messages_in_date_range(
            ldap_list=ldap_list,
            start_date=start_date,
            end_date=end_date,
        )

        return api_response(
            success=True,
            message="Successfully.",
            data=response,
            status_code=HTTPStatus.OK,
        )

    def get_all_jira_projects_api(self):
        """API endpoint to get a mapping of all project IDs to their names."""
        jira_data = self.jira_analytics_service.get_all_jira_projects()

        return api_response(
            success=True,
            message="Fetch jira projects successful",
            data=jira_data,
            status_code=HTTPStatus.OK,
        )

    def get_all_calendars_api(self):
        """API endpoint to get Google Calendar list from Redis."""
        calendar_data = self.google_calendar_analytics_service.get_all_calendars()

        return api_response(
            success=True,
            message="Calendar list fetched successfully.",
            data=calendar_data,
            status_code=HTTPStatus.OK,
        )

    def get_all_events_api(self):
        """
        API endpoint to get Google Calendar events for users from Redis.

        Request JSON Body:
            calendarIds (List[str]): List of calendar IDs to fetch events from.
            ldaps (List[str]): List of LDAP usernames.
            startDate (str): ISO 8601 start datetime (inclusive).
            endDate (str): ISO 8601 end datetime (exclusive).

        Returns:
            JSON: A dictionary mapping each LDAP to a list of event attendance details.

        TODO:
            This method currently calls `get_all_events` in a loop for each calendar,
            which increases round-trip time (RTT) proportionally to the number of calendars.
            Consider enhancing `get_all_events` to support fetching events from multiple
            calendars in a single call to reduce RTT and improve overall performance.
        """
        data = request.get_json(silent=True) or {}
        calendar_ids = data.get("calendarIds", [])
        ldaps = data.get("ldaps", [])
        start_date = data.get("startDate")
        end_date = data.get("endDate")

        if not calendar_ids:
            return api_response(
                success=False,
                message="Missing required query parameters: calendar_ids.",
                status_code=HTTPStatus.BAD_REQUEST,
            )

        start_dt, end_dt = self.date_time_util.get_start_end_timestamps(
            start_date, end_date
        )

        calendar_data = (
            self.google_calendar_analytics_service.get_all_events_from_calendars(
                calendar_ids,
                ldaps,
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

    async def get_gerrit_stats(self):
        """API endpoint to retrieve aggregated Gerrit stats."""
        body = request.get_json(silent=True) or {}

        response = self.gerrit_analytics_service.get_gerrit_stats(
            ldap_list=body.get("ldaps"),
            start_date_str=body.get("startDate"),
            end_date_str=body.get("endDate"),
            project_list=body.get("project"),
        )

        return api_response(
            success=True,
            message="Successfully.",
            data=response,
            status_code=HTTPStatus.OK,
        )

    def get_gerrit_projects(self):
        """API endpoint to retrieve the list of Gerrit projects."""
        projects = self.gerrit_analytics_service.get_gerrit_projects()
        return api_response(
            success=True,
            message="Successfully retrieved Gerrit projects.",
            data=projects,
            status_code=HTTPStatus.OK,
        )


@frontend_bp.route("/summary", methods=["POST"])
def get_summary():
    """
    TODO: [PUR-116] Implement /api/summary

    Provides a comprehensive summary of team activities and key metrics.
    This is a temporary endpoint and will be fully implemented later.

    Request Body (JSON):
        {
            "startDate": "YYYY-MM-DD",
            "endDate": "YYYY-MM-DD",
            "groups": ["<group1>", "<group2>"],
            "includeTerminated": boolean
        }
    """
    return api_response(
        success=False, message="Not Implemented", status_code=HTTPStatus.NOT_IMPLEMENTED
    )
