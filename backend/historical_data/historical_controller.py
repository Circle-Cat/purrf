from http import HTTPStatus
from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.common.fast_api_response_wrapper import api_response
from backend.common.user_role import UserRole
from backend.utils.permission_decorators import authenticate
from backend.common.api_endpoints import (
    MICROSOFT_BACKFILL_LDAPS_ENDPOINT,
    MICROSOFT_BACKFILL_CHAT_MESSAGES_ENDPOINT,
    JIRA_SYNC_PROJECTS_ENDPOINT,
    JIRA_BACKFILL_ISSUES_ENDPOINT,
    JIRA_UPDATE_ISSUES_ENDPOINT,
    GOOGLE_CALENDAR_PULL_HISTORY_ENDPOINT,
    GERRIT_BACKFILL_CHANGES_ENDPOINT,
    GERRIT_BACKFILL_PROJECTS_ENDPOINT,
    GOOGLE_CHAT_SYNC_HISTORY_MESSAGES_ENDPOINT,
)


class GoogleCalendarPullRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None


class GerritBackfillRequest(BaseModel):
    statuses: list[str] | None = None


class HistoricalController:
    def __init__(
        self,
        microsoft_member_sync_service,
        microsoft_chat_history_sync_service,
        jira_history_sync_service,
        google_calendar_sync_service,
        date_time_utils,
        gerrit_sync_service,
        google_chat_history_sync_service,
    ):
        """
        Initialize the HistoricalController with required dependencies.

        Args:
            microsoft_member_sync_service: MicrosoftMemberSyncService instance.
            microsoft_chat_history_sync_service: MicrosoftChatHistorySyncService instance.
            jira_history_sync_service: JiraHistorySyncService instance
            google_calendar_sync_service: GoogleCalendarSyncService instance.
            date_time_utils: DateTimeUtil instance.
            gerrit_sync_service: GerritSyncService instance.
            google_chat_history_sync_service: GoogleChatHistorySyncService instance
        """
        self.microsoft_member_sync_service = microsoft_member_sync_service
        self.microsoft_chat_history_sync_service = microsoft_chat_history_sync_service
        self.jira_history_sync_service = jira_history_sync_service
        self.google_calendar_sync_service = google_calendar_sync_service
        self.date_time_utils = date_time_utils
        self.gerrit_sync_service = gerrit_sync_service
        self.google_chat_history_sync_service = google_chat_history_sync_service

        self.router = APIRouter(tags=["history"])

        self.router.add_api_route(
            MICROSOFT_BACKFILL_LDAPS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN, UserRole.CRON_RUNNER])(
                self.backfill_microsoft_ldaps
            ),
            methods=["POST"],
        )
        self.router.add_api_route(
            MICROSOFT_BACKFILL_CHAT_MESSAGES_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.backfill_microsoft_chat_messages
            ),
            methods=["POST"],
        )
        self.router.add_api_route(
            JIRA_SYNC_PROJECTS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN, UserRole.CRON_RUNNER])(
                self.sync_jira_projects
            ),
            methods=["POST"],
        )
        self.router.add_api_route(
            JIRA_BACKFILL_ISSUES_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.backfill_jira_issues),
            methods=["POST"],
        )
        self.router.add_api_route(
            JIRA_UPDATE_ISSUES_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN, UserRole.CRON_RUNNER])(
                self.update_jira_issues
            ),
            methods=["POST"],
        )
        self.router.add_api_route(
            GOOGLE_CALENDAR_PULL_HISTORY_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN, UserRole.CRON_RUNNER])(
                self.pull_calendar_history_api
            ),
            methods=["POST"],
        )
        self.router.add_api_route(
            GERRIT_BACKFILL_CHANGES_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.backfill_gerrit_changes),
            methods=["POST"],
        )
        self.router.add_api_route(
            GERRIT_BACKFILL_PROJECTS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.backfill_gerrit_projects
            ),
            methods=["POST"],
        )
        self.router.add_api_route(
            GOOGLE_CHAT_SYNC_HISTORY_MESSAGES_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.sync_google_chat_history_messages
            ),
            methods=["POST"],
        )

    async def sync_google_chat_history_messages(self):
        """API endpoint to trigger the fetching of messages for all SPACE type Google chat spaces."""
        result = self.google_chat_history_sync_service.sync_history_messages()
        return api_response(
            success=True,
            message="Google Chat messages saved successfully.",
            data=result,
            status_code=HTTPStatus.OK,
        )

    async def update_jira_issues(self, hours: int = Query(None)):
        """
        Incrementally update Jira issues in Redis.
        Query parameter: hours (int)
        """
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
            message=f"Incremental Jira issues updated successfully for for the past {hours} hour(s).",
            data={"updated_issues": result},
            status_code=HTTPStatus.OK,
        )

    async def backfill_jira_issues(self):
        """Backfill all Jira issues into Redis."""
        result = self.jira_history_sync_service.backfill_all_jira_issues()
        return api_response(
            success=True,
            message="Full Jira issues backfill completed successfully.",
            data=result,
            status_code=HTTPStatus.OK,
        )

    async def backfill_microsoft_ldaps(self):
        """API endpoint to backfill Microsoft 365 user LDAP information into Redis."""
        await self.microsoft_member_sync_service.sync_microsoft_members_to_redis()
        return api_response(
            success=True,
            message="Microsoft 365 user LDAP information backfilled successfully.",
            data=None,
            status_code=HTTPStatus.OK,
        )

    async def backfill_microsoft_chat_messages(self, chatId: str):
        """API endpoint to backfill Microsoft Teams Chat messages into Redis."""
        await self.microsoft_chat_history_sync_service.sync_microsoft_chat_messages_by_chat_id(
            chatId
        )
        return api_response(
            success=True,
            message=f"Microsoft Teams chat messages for chat ID {chatId} backfilled successfully.",
            data=None,
            status_code=HTTPStatus.OK,
        )

    async def sync_jira_projects(self):
        """Import all Jira project IDs and their display names into Redis."""
        result = self.jira_history_sync_service.sync_jira_projects_id_and_name_mapping()
        return api_response(
            success=True,
            message="Jira projects imported successfully.",
            data={"imported_projects": result},
            status_code=HTTPStatus.OK,
        )

    async def pull_calendar_history_api(self, request_body: GoogleCalendarPullRequest):
        """
        Endpoint to trigger fetching and caching Google Calendar history.
        """
        time_min, time_max = self.date_time_utils.resolve_start_end_timestamps(
            request_body.start_date, request_body.end_date
        )

        self.google_calendar_sync_service.pull_calendar_history(time_min, time_max)

        return api_response(
            success=True,
            message=f"Google Calendar history pulled and cached from {time_min} to {time_max}.",
            data=None,
            status_code=HTTPStatus.OK,
        )

    async def backfill_gerrit_changes(self, request_body: GerritBackfillRequest):
        """API endpoint to backfill Gerrit changes into Redis."""
        self.gerrit_sync_service.fetch_and_store_changes(statuses=request_body.statuses)

        return api_response(
            success=True,
            message="Gerrit changes backfilled successfully.",
            data="",
            status_code=HTTPStatus.OK,
        )

    async def backfill_gerrit_projects(self):
        """API endpoint to backfill Gerrit projects into Redis."""
        count = self.gerrit_sync_service.sync_gerrit_projects()

        return api_response(
            success=True,
            message="Gerrit projects backfilled successfully.",
            data={"project_count": count},
            status_code=HTTPStatus.OK,
        )
