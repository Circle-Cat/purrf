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

    def __init__(self, logger, gmail_sync_service, database):
        """
        Args:
            logger: Logger instance.
            gmail_sync_service (GmailSyncService): Renews the watch and syncs mailboxes.
            database: Async session provider.
        """
        self.logger = logger
        self.gmail_sync_service = gmail_sync_service
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

        Called by the daily CronJob. Errors propagate so the job fails and
        Kubernetes retries it; the alert email was already sent. A failed
        renewal still catches up first, since the current watch may have days
        left, and its error is the one raised.
        """
        async with self.database.session() as session:
            try:
                watch = await self.gmail_sync_service.renew_watch(session)
            except Exception:
                await session.rollback()
                try:
                    await self.gmail_sync_service.catch_up(session)
                except Exception:
                    self.logger.exception(
                        "[GmailSync] catch-up after a failed watch renewal failed"
                    )
                raise
            catch_up = await self.gmail_sync_service.catch_up(session)
        return api_response(
            message="Gmail watch renewed.",
            data={"watch": watch, "catchUp": catch_up},
        )

    async def resync(
        self, current_user: UserContextDto, background_tasks: BackgroundTasks
    ):
        """Start a full resync of every tracked thread and return at once.

        The resync outlasts the edge proxy's request timeout, so it runs as a
        background task; its outcome is in the log and, on failure, the alert.
        """
        background_tasks.add_task(self._run_full_resync)
        return api_response(
            message="Full resync started.", status_code=HTTPStatus.ACCEPTED
        )

    async def _run_full_resync(self):
        try:
            async with self.database.session() as session:
                await self.gmail_sync_service.full_resync(session, alert=False)
        except Exception:
            self.logger.exception("[GmailSync] manual full resync failed")
