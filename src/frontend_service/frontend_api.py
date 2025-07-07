from flask import Blueprint, request
from http import HTTPStatus
from src.frontend_service.ldap_loader import get_all_ldaps_and_displaynames
from src.frontend_service.chat_query_utils import count_messages_in_date_range
from src.common.constants import MicrosoftAccountStatus
from src.common.api_response_wrapper import api_response
from src.utils.google_chat_utils import get_chat_spaces

frontend_bp = Blueprint("frontend", __name__, url_prefix="/api")


@frontend_bp.route("/microsoft/<status>/ldaps", methods=["GET"])
async def all_ldaps_and_names(status):
    """API endpoint to get Microsoft 365 user LDAP information from Redis."""
    response = get_all_ldaps_and_displaynames(
        MicrosoftAccountStatus.validate_status(status)
    )

    return api_response(
        success=True,
        message="Saved successfully.",
        data=response,
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