from flask import Blueprint, request
from http import HTTPStatus
from backend.frontend_service.chat_query_utils import count_messages_in_date_range
from backend.frontend_service.jira_loader import process_get_issue_detail_batch
from backend.frontend_service.gerrit_loader import (
    get_gerrit_stats as load_gerrit_stats,
)
from backend.frontend_service.calendar_loader import (
    get_all_calendars,
    get_all_events,
)
from backend.common.constants import MicrosoftAccountStatus, MicrosoftGroups
from backend.common.api_response_wrapper import api_response
from backend.utils.google_chat_utils import get_chat_spaces
from backend.frontend_service.microsoft_chat_topics_loader import (
    get_microsoft_chat_topics,
)
from backend.frontend_service.jira_loader import get_issue_ids_in_timerange


frontend_bp = Blueprint("frontend", __name__, url_prefix="/api")


class FrontendController:
    def __init__(self, ldap_service):
        """
        Initialize the FrontendController with required dependencies.

        Args:
            ldap_service: LdapService instance.
        """
        self.ldap_service = ldap_service

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


@frontend_bp.route("/google/chat/count", methods=["GET"])
def count_messages():
    """
    Count chat messages in Redis within a specified date range.

    Redis keys are structured as "{space_id}/{sender_ldap}", and this endpoint
    counts the number of messages (sorted set entries) whose UNIX timestamp
    score falls within the requested date range.

    Query Parameters:
        spaceId (str, optional): Repeated key format (e.g., "spaceId=space1&spaceId=space2").
            If omitted, all space IDs are included.

        senderLdap (str, optional): Repeated key format (e.g., "senderLdap=alice&senderLdap=bob").
            If omitted, all sender LDAPs are included.

        startDate (str, optional): Start date in "YYYY-MM-DD" format.
            Defaults to one month before endDate.

        endDate (str, optional): End date in "YYYY-MM-DD" format.
            Defaults to today (UTC).

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

    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")

    space_ids = request.args.getlist("spaceId")
    sender_ldaps = request.args.getlist("senderLdap")

    result = count_messages_in_date_range(
        space_ids=space_ids,
        sender_ldaps=sender_ldaps,
        start_date=start_date,
        end_date=end_date,
    )

    return api_response(
        success=True,
        message="Messages counted successfully.",
        data=result,
        status_code=HTTPStatus.OK,
    )


@frontend_bp.route("/google/chat/spaces", methods=["GET"])
def get_chat_spaces_route():
    """API endpoint to retrieve chat spaces of a specified type and page size."""

    space_type = request.args.get("space_type", "SPACE")
    page_size = int(request.args.get("page_size", 100))

    spaces = get_chat_spaces(space_type, page_size)
    return api_response(
        success=True,
        message="Retrieve chat spaces successfully.",
        data=spaces,
        status_code=HTTPStatus.OK,
    )


@frontend_bp.route("/microsoft/chat/topics", methods=["GET"])
async def all_microsoft_chat_topics():
    """Fetch Microsoft chat topics from Redis."""
    response = await get_microsoft_chat_topics()

    return api_response(
        success=True,
        message="Successfully.",
        data=response,
        status_code=HTTPStatus.OK,
    )


@frontend_bp.route("/jira/brief", methods=["POST"])
def get_issue_ids():
    """
    Get Jira issue IDs in Redis by status: done, in_progress, todo, and all.

    Request body (JSON):
        {
            "status": "<status>",  # required, one of "done", "in_progress", "todo", "all"
            "ldaps": ["<ldap>", ...],  # required
            "project_ids": ["<project_id>", ...],  # required
            "start_date": "<yyyy-mm-dd>",  # required for "done"/"all"
            "end_date": "<yyyy-mm-dd>"     # required for "done"/"all"
        }

    Returns:
        Response (JSON): Standard API response with issue IDs grouped by status, ldap and project.
    """
    data = request.get_json(force=True)
    status = data.get("status")
    ldaps = data.get("ldaps")
    project_ids = data.get("project_ids")
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    result = get_issue_ids_in_timerange(
        status=status,
        ldaps=ldaps,
        project_ids=project_ids,
        start_date=start_date,
        end_date=end_date,
    )

    return api_response(
        success=True,
        message="Issue IDs retrieved successfully.",
        data=result,
        status_code=HTTPStatus.OK,
    )


@frontend_bp.route("/gerrit/stats", methods=["GET"])
async def get_gerrit_stats():
    """API endpoint to retrieve aggregated Gerrit stats."""

    response = load_gerrit_stats(
        raw_ldap=request.args.get("ldap_list"),
        start_date_str=request.args.get("start_date"),
        end_date_str=request.args.get("end_date"),
        raw_project=request.args.get("project"),
    )

    return api_response(
        success=True,
        message="Fetched Gerrit stats successfully.",
        data=response,
        status_code=HTTPStatus.OK,
    )


@frontend_bp.route("/google/calendar/calendars", methods=["GET"])
def get_all_calendars_api():
    """API endpoint to get Google Calendar list from Redis."""
    calendar_data = get_all_calendars()

    return api_response(
        success=True,
        message="Calendar list fetched successfully.",
        data=calendar_data,
        status_code=HTTPStatus.OK,
    )


@frontend_bp.route("/jira/detail/batch", methods=["POST"])
def get_issue_detail_batch():
    """
    Get Jira issue details in batch from Redis.

    Fetch the full metadata of multiple Jira issues from Redis, given a list
    of issue_ids.

    Request Body (JSON):
        A list of issue_ids.

    Returns:
        JSON response with success flag, message, and data containing issue
        details.

    Raises:
        400 Bad Request: If issue_ids is missing or invalid
        500 Internal Server Error: If Redis operations fail
    """
    data = request.get_json()
    issue_ids = data.get("issue_ids") if data else None

    result = process_get_issue_detail_batch(issue_ids)

    return api_response(
        success=True,
        message="Query successful",
        data=result,
        status_code=HTTPStatus.OK,
    )


@frontend_bp.route("/google/calendar/events", methods=["GET"])
def get_all_events_api():
    """
    API endpoint to get Google Calendar events for users from Redis.

    Query Parameters:
        calendar_id (str): The calendar ID to fetch events from.
        ldaps (str): Comma-separated list of LDAP usernames.
        start_date (str): ISO 8601 start datetime (inclusive).
        end_date (str): ISO 8601 end datetime (exclusive).

    Returns:
        JSON: A dictionary mapping each LDAP to a list of event attendance details.
    """
    calendar_id = request.args.get("calendar_id")
    ldaps_str = request.args.get("ldaps", "")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not calendar_id or not start_date or not end_date:
        return api_response(
            success=False,
            message="Missing required query parameters: calendar_id, start_date, end_date.",
            status_code=HTTPStatus.BAD_REQUEST,
        )

    ldaps = [ldap.strip() for ldap in ldaps_str.split(",") if ldap.strip()]

    calendar_data = get_all_events(calendar_id, ldaps, start_date, end_date)
    return api_response(
        success=True,
        message="Calendar events fetched successfully.",
        data=calendar_data,
        status_code=HTTPStatus.OK,
    )
