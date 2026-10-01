from http import HTTPStatus

from fastapi import APIRouter, BackgroundTasks

from backend.common.api_endpoints import (
    GMAIL_FULL_RESYNC_ENDPOINT,
    GMAIL_WATCH_MAINTAIN_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate


class GmailSyncController:
    """Operational endpoints for the Gmail sync: daily maintenance and a manual full resync."""

    def __init__(self, gmail_maintenance_service, database):
        """
        Args:
            gmail_maintenance_service (GmailMaintenanceService): Runs the
                maintenance and the manual resync.
            database: Async session provider.
        """
        self.gmail_maintenance_service = gmail_maintenance_service
        self.database = database
        self.router = APIRouter(tags=["gmail-sync"])
        self.router.add_api_route(
            GMAIL_WATCH_MAINTAIN_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.SYSTEM_SYNC])(self.maintain),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            GMAIL_FULL_RESYNC_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.OPS_MAINTAIN])(self.resync),
            methods=["POST"],
            response_model=None,
            status_code=HTTPStatus.ACCEPTED,
        )

    async def maintain(self, current_user: UserContextDto):
        """Renew the Gmail watch, then catch up from the cursor.

        Called by the daily CronJob. Errors propagate so the job fails.
        """
        async with self.database.session() as session:
            data = await self.gmail_maintenance_service.maintain(session)
        return api_response(message="Gmail watch renewed.", data=data)

    async def resync(
        self, current_user: UserContextDto, background_tasks: BackgroundTasks
    ):
        """Start a full resync of every tracked thread and return at once.

        The resync outlasts the edge proxy's request timeout, so it runs as a
        background task; its outcome is in the log and, on failure, the alert.
        """
        background_tasks.add_task(self.gmail_maintenance_service.run_manual_full_resync)
        return api_response(
            message="Full resync started.", status_code=HTTPStatus.ACCEPTED
        )
