from flask import Blueprint, request
from http import HTTPStatus
from backend.historical_data.gerrit_history_fetcher import fetch_and_store_changes
from backend.historical_data.google_chat_history_fetcher import fetch_history_messages
from backend.historical_data.google_calendar_history_fetcher import (
    pull_calendar_history,
)
from backend.common.api_response_wrapper import api_response
from backend.utils.date_time_util import get_start_end_timestamps
from datetime import datetime, timedelta, timezone

history_bp = Blueprint("history", __name__, url_prefix="/api")


class HistoricalController:
    def __init__(
        self,
        microsoft_member_sync_service,
        microsoft_chat_history_sync_service,
        jira_history_sync_service,
    ):
        """
        Initialize the HistoricalController with required dependencies.

        Args:
            microsoft_member_sync_service: MicrosoftMemberSyncService instance.
            microsoft_chat_history_sync_service: MicrosoftChatHistorySyncService instance.
            jira_history_sync_service: JiraHistorySyncService instance
        """
        self.microsoft_member_sync_service = microsoft_member_sync_service
        self.microsoft_chat_history_sync_service = microsoft_chat_history_sync_service
        self.jira_history_sync_service = jira_history_sync_service

    def register_routes(self, blueprint):
        """
        Register all historical data backfill routes to the given Flask blueprint.

        Args:
            blueprint: Flask Blueprint object to register routes on.
        """
        blueprint.add_url_rule(
            "/microsoft/backfill/ldaps",
            view_func=self.backfill_microsoft_ldaps,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/microsoft/backfill/chat/messages/<chatId>",
            view_func=self.backfill_microsoft_chat_messages,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/jira/project",
            view_func=self.sync_jira_projects,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/jira/backfill",
            view_func=self.backfill_jira_issues,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/jira/update",
            view_func=self.update_jira_issues,
            methods=["POST"],
        )

    def update_jira_issues(self):
        """
        Incrementally update Jira issues in Redis for issues created or updated within the last N hours.
        This endpoint performs an incremental sync (created + updated).
        Query parameter: hours (int)
        """
        hours = request.args.get("hours", default=None, type=int)
        if hours is None or hours <= 0:
            return api_response(
                success=False,
                message="Missing or invalid 'hours' query parameter.",
                data={},
                status_code=HTTPStatus.BAD_REQUEST,
            )

        result = self.jira_history_sync_service.process_update_jira_issues(hours)
        return api_response(
            success=True,
            message="Updated successfully",
            data={"updated_issues": result},
            status_code=HTTPStatus.OK,
        )

    def backfill_jira_issues(self):
        """Backfill all Jira issues into Redis. This endpoint does not accept
        any parameters.
        """
        result = self.jira_history_sync_service.backfill_all_jira_issues()
        return api_response(
            success=True,
            message="Imported successfully",
            data=result,
            status_code=HTTPStatus.OK,
        )

    async def backfill_microsoft_ldaps(self):
        """
        API endpoint to backfill Microsoft 365 user LDAP information into Redis.
        """

        await self.microsoft_member_sync_service.sync_microsoft_members_to_redis()

        return api_response(
            success=True,
            message="Successfully.",
            data=None,
            status_code=HTTPStatus.OK,
        )

    async def backfill_microsoft_chat_messages(self, chatId):
        """API endpoint to backfill Microsoft Teams Chat messages into Redis."""
        await self.microsoft_chat_history_sync_service.sync_microsoft_chat_messages_by_chat_id(
            chatId
        )

        return api_response(
            success=True,
            message="Saved successfully.",
            data=None,
            status_code=HTTPStatus.OK,
        )

    def sync_jira_projects(self):
        """Import all Jira project IDs and their display names into Redis."""

        result = self.jira_history_sync_service.sync_jira_projects_id_and_name_mapping()

        return api_response(
            success=True,
            message="Imported successfully",
            data={"imported_projects": result},
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

    if not start_date_str and not end_date_str:
        end_dt_utc = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_dt_utc = end_dt_utc - timedelta(days=1)
    else:
        start_dt_utc, end_dt_utc = get_start_end_timestamps(
            start_date_str, end_date_str
        )

    time_min = start_dt_utc.isoformat().replace("+00:00", "Z")
    time_max = end_dt_utc.isoformat().replace("+00:00", "Z")

    pull_calendar_history(time_min, time_max)

    return api_response(
        success=True,
        message=f"Google Calendar history pulled and cached from {time_min} to {time_max}.",
        data=None,
        status_code=HTTPStatus.OK,
    )
