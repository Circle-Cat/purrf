"""FastAPI routes for the admin side of leave."""

from backend.common.api_endpoints import LEAVE_ADJUSTMENTS_ENDPOINT
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.leave_adjustment_dto import LeaveAdjustmentRequestDto
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate
from fastapi import APIRouter


class LeaveAdminController:
    """Admin-only leave routes, gated by ``Permission.LEAVE_ADMIN``.

    Reading the calendar or one's own balance needs no permission; changing
    somebody's hours by hand does.
    """

    def __init__(self, leave_adjustment_service, database):
        """
        Args:
            leave_adjustment_service (LeaveAdjustmentService): Hand-written
                ledger corrections.
            database: Async session provider.
        """
        self.leave_adjustment_service = leave_adjustment_service
        self.database = database
        self.router = APIRouter(tags=["leave-admin"])

        self.router.add_api_route(
            LEAVE_ADJUSTMENTS_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.LEAVE_ADMIN])(self.adjust),
            methods=["POST"],
            response_model=None,
        )

    async def adjust(
        self, payload: LeaveAdjustmentRequestDto, current_user: UserContextDto
    ):
        """Append one hand-written correction to somebody's ledger.

        The author is whoever signed in, never a field in the body.
        """
        async with self.database.session() as session:
            result = await self.leave_adjustment_service.adjust(
                session,
                user_id=payload.user_id,
                hours=payload.hours,
                effective_date=payload.effective_date,
                note=payload.note,
                author_user_id=current_user.user_id,
            )
        return api_response(message="Leave balance adjusted.", data=result)
