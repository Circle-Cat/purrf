from flask import Blueprint, jsonify, request
from redis_dal.redis_query_utils import count_messages_in_date_range
from http import HTTPStatus

redis_api = Blueprint("redis_api", __name__)


@redis_api.route("/chat/count", methods=["GET"])
def count_messages():
    """
    Count chat messages in Redis within a specified date range.

    Redis keys are structured as "{space_id}/{sender_ldap}", and this endpoint counts
    the number of messages (sorted set entries) whose UNIX timestamp score falls within
    the requested date range.

    Query Parameters:
        spaceId (str, optional): Comma-separated list of space IDs
            (e.g., "space1,space2"). If omitted, all space IDs are included.
        senderLdap (str, optional): Comma-separated list of sender LDAPs
            (e.g., "alice,bob"). If omitted, all LDAPs are included.
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

    space_id_param = request.args.get("spaceId")
    sender_ldap_param = request.args.get("senderLdap")

    # TODO: Move comma-separated param parsing to a separate formatter layer
    space_ids = (
        [s.strip() for s in space_id_param.split(",") if s.strip()]
        if space_id_param
        else None
    )
    sender_ldaps = (
        [s.strip() for s in sender_ldap_param.split(",") if s.strip()]
        if sender_ldap_param
        else None
    )

    result = count_messages_in_date_range(
        space_ids=space_ids,
        sender_ldaps=sender_ldaps,
        start_date=start_date,
        end_date=end_date,
    )

    return jsonify(result), HTTPStatus.OK
