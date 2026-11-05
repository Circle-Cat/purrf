"""The two scheduled leave endpoints, called by CronJobs."""

from backend.common.api_endpoints import (
    LEAVE_ANNUAL_CLOSE_JOB_ENDPOINT,
    LEAVE_WEEKLY_ACCRUAL_JOB_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.utils.permission_decorators import authenticate
from fastapi import APIRouter


class LeaveJobController:
    """Triggers for the accrual engine, reserved for the scheduler.

    Both routes write to everybody's ledger, so they are gated on
    ``SYSTEM_BACKFILL_SCHEDULED`` -- a service-account permission no signed-in
    person holds. Neither answers a GET: a pay-out is not something a browser
    should be able to cause by loading a URL.

    Each returns its run's report. The report is the only place the people who
    were skipped are named, and being skipped is invisible in a balance.
    """

    def __init__(self, leave_engine_service, database):
        """
        Args:
            leave_engine_service (LeaveEngineService): The two jobs.
            database: Async session provider.
        """
        self.leave_engine_service = leave_engine_service
        self.database = database
        self.router = APIRouter(tags=["leave-jobs"])

        self.router.add_api_route(
            LEAVE_WEEKLY_ACCRUAL_JOB_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.SYSTEM_BACKFILL_SCHEDULED])(
                self.run_weekly_accrual
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            LEAVE_ANNUAL_CLOSE_JOB_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.SYSTEM_BACKFILL_SCHEDULED])(
                self.run_annual_close
            ),
            methods=["POST"],
            response_model=None,
        )

    async def run_weekly_accrual(self):
        """Accrue everybody a week's entitlement, as at the Beijing day now."""
        async with self.database.session() as session:
            report = await self.leave_engine_service.run_weekly_accrual(session)
        return api_response(message="Leave accrual run.", data=report)

    async def run_annual_close(self):
        """Close out the year that just ended, then apply the carryover cap."""
        async with self.database.session() as session:
            report = await self.leave_engine_service.run_annual_close(session)
        return api_response(message="Leave year closed.", data=report)
