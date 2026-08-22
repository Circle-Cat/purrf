"""FastAPI routes for the company holiday calendar."""

from backend.common.api_endpoints import (
    LEAVE_HOLIDAY_YEARS_ENDPOINT,
    LEAVE_HOLIDAYS_YEAR_ENDPOINT,
    LEAVE_POLICY_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.leave_holiday_dto import LeaveCalendarReplaceRequestDto
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate
from fastapi import APIRouter


class LeaveCalendarController:
    """Company holiday routes: three reads open to any signed-in employee, one
    write gated by ``Permission.LEAVE_ADMIN``.

    The reads are deliberately ungated. Company holidays are reference
    information everyone works from, and the employee-side dialog reads these
    same routes -- putting LEAVE_ADMIN on them would either 403 the whole
    company or force a duplicate endpoint later. Entering the calendar is the
    privileged action.
    """

    def __init__(self, leave_calendar_service, database):
        """
        Args:
            leave_calendar_service (LeaveCalendarService): Calendar business
                logic.
            database: Async session provider.
        """
        self.leave_calendar_service = leave_calendar_service
        self.database = database
        self.router = APIRouter(tags=["leave-calendar"])

        self.router.add_api_route(
            LEAVE_HOLIDAYS_YEAR_ENDPOINT,
            endpoint=authenticate()(self.get_year),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            LEAVE_HOLIDAYS_YEAR_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.LEAVE_ADMIN])(
                self.replace_year
            ),
            methods=["PUT"],
            response_model=None,
        )
        self.router.add_api_route(
            LEAVE_HOLIDAY_YEARS_ENDPOINT,
            endpoint=authenticate()(self.list_years),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            LEAVE_POLICY_ENDPOINT,
            endpoint=authenticate()(self.get_policy),
            methods=["GET"],
            response_model=None,
        )

    async def get_year(self, year: int):
        """Return one year of company holidays, grouped into segments."""
        async with self.database.session() as session:
            calendar = await self.leave_calendar_service.get_year(session, year)
        return api_response(message="Company holidays fetched.", data=calendar)

    async def replace_year(
        self,
        year: int,
        payload: LeaveCalendarReplaceRequestDto,
        current_user: UserContextDto,
    ):
        """Replace one year of company holidays with the segments given.

        The whole year is replaced, so anything absent from the payload is
        deleted. What comes back is read from storage rather than echoed.
        """
        async with self.database.session() as session:
            calendar = await self.leave_calendar_service.replace_year(
                session, year, payload.segments
            )
        return api_response(message="Company holidays saved.", data=calendar)

    async def list_years(self):
        """Return the years holding holidays, plus this year and next."""
        async with self.database.session() as session:
            years = await self.leave_calendar_service.list_years(session)
        return api_response(message="Company holiday years fetched.", data=years)

    async def get_policy(self):
        """Return the read-only leave constants. Reads nothing: they are code."""
        return api_response(
            message="Leave policy fetched.",
            data=self.leave_calendar_service.get_policy(),
        )
