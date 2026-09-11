"""FastAPI routes for leave balance and ledger queries."""

from fastapi import APIRouter

from backend.common.api_endpoints import LEAVE_BALANCE_ENDPOINT
from backend.common.fast_api_response_wrapper import api_response
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate


class LeaveBalanceController:
    """Leave balance routes: queries an employee's total balance and ledger history."""

    def __init__(self, leave_balance_service, database):
        """
        Args:
            leave_balance_service (LeaveBalanceService): Balance business logic.
            database: Async session provider.
        """
        self.leave_balance_service = leave_balance_service
        self.database = database
        self.router = APIRouter(tags=["leave-balance"])

        self.router.add_api_route(
            LEAVE_BALANCE_ENDPOINT,
            endpoint=authenticate()(self.get_balance),
            methods=["GET"],
            response_model=None,
        )

    async def get_balance(self, current_user: UserContextDto):
        """Return the current user's leave balance and complete ledger history.

        No user_id is accepted from the path or query: the balance is strictly for
        the authenticated user attached to the token.
        """
        async with self.database.session() as session:
            balance_data = await self.leave_balance_service.get_leave_balance(
                session, current_user.user_id
            )
        return api_response(message="Leave balance fetched.", data=balance_data)