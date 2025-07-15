from flask import Blueprint, request
from http import HTTPStatus
from src.historical_data.microsoft_ldap_fetcher import sync_microsoft_members_to_redis
from src.historical_data.gerrit_history_fetcher import fetch_and_store_changes
from src.historical_data.google_chat_history_fetcher import fetch_history_messages
from src.historical_data.jira_history_fetcher import process_sync_jira_projects
from src.historical_data.google_calendar_history_fetcher import pull_calendar_history
from src.common.api_response_wrapper import api_response
from src.historical_data.microsoft_chat_history_fetcher import (
    sync_microsoft_chat_messages_by_chat_id,
)
from src.utils.date_time_parser import get_start_end_timestamps

history_bp = Blueprint("history", __name__, url_prefix="/api")


@history_bp.route("/microsoft/backfill/ldaps", methods=["POST"])
async def backfill_microsoft_ldaps():
    """API endpoint to backfill Microsoft 365 user LDAP information into Redis."""

    response = await sync_microsoft_members_to_redis()

    return api_response(
        success=True,
        message="Saved successfully.",
        data=response,
        status_code=HTTPStatus.OK,
    )


@history_bp.route("/gerrit/backfill", methods=["POST"])
async def backfill_gerrit_changes():
    """API endpoint to backfill Gerrit changes into Redis."""

    body = request.get_json(silent=True) or {}
    statuses = body.get("statuses")

    fetch_and_store_changes(statuses=statuses)

    return api_response(
        success=True,
        message="Saved successfully.",
        data="",
        status_code=HTTPStatus.OK,
    )


@history_bp.route("/microsoft/fetch/history/messages/<chatId>", methods=["POST"])
async def backfill_microsoft_chat_messages(chatId):
    """API endpoint to backfill Microsoft Teams Chat messages into Redis."""
    response = await sync_microsoft_chat_messages_by_chat_id(chatId)

    return api_response(
        success=True,
        message="Saved successfully.",
        data=response,
        status_code=HTTPStatus.OK,
    )


@history_bp.route("/google/chat/spaces/messages", methods=["POST"])
def history_messages():
    """API endpoint to trigger the fetching of messages for all SPACE type chat spaces and store them in Redis asynchronously."""

    response = fetch_history_messages()
    return api_response(
        success=True,
        message="Saved successfully.",
        data=response,
        status_code=HTTPStatus.OK,
    )


@history_bp.route("/jira/project", methods=["POST"])
def sync_jira_projects():
    """Import all Jira project IDs and their display names into Redis."""
    result = process_sync_jira_projects()
    return api_response(
        success=True,
        message="Imported successfully",
        data={"imported_projects": result},
        status_code=HTTPStatus.OK,
    )


@history_bp.route("/google/calendar/history/pull", methods=["POST"])
def pull_calendar_history_api():
    """
    Endpoint to trigger fetching and caching Google Calendar history.

    Request JSON params (optional):
      - start_date: ISO format string, start of time range (default: now - 24h)
      - end_date: ISO format string, end of time range (default: now)
    """
    data = request.get_json(silent=True) or {}

    start_date_str = data.get("start_date")  # Expecting "YYYY-MM-DD"
    end_date_str = data.get("end_date")  # Expecting "YYYY-MM-DD"

    start_dt_utc, end_dt_utc = get_start_end_timestamps(start_date_str, end_date_str)

    time_min = start_dt_utc.isoformat().replace("+00:00", "Z")
    time_max = end_dt_utc.isoformat().replace("+00:00", "Z")

    pull_calendar_history(time_min, time_max)

    return api_response(
        success=True,
        message=f"Google Calendar history pulled and cached from {time_min} to {time_max}.",
        data=None,
        status_code=HTTPStatus.OK,
    )
