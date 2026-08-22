"""Routes and gating for the company holiday calendar."""

import datetime
import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.permissions import Permission
from backend.dto.leave_holiday_dto import (
    LeaveCalendarReplaceRequestDto,
    LeaveCalendarYearDto,
    LeaveHolidaySegmentInputDto,
    LeaveHolidayYearsDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.leave.leave_calendar_controller import LeaveCalendarController
from backend.leave.leave_policy import current_policy


def _route_permissions(route):
    """The permission list closed over by the authenticate decorator, or None
    for a route that only requires a logged-in user."""
    free_variables = route.endpoint.__code__.co_freevars
    if "permissions" not in free_variables:
        return None
    return route.endpoint.__closure__[free_variables.index("permissions")].cell_contents


class TestLeaveCalendarController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.service = MagicMock()
        self.service.get_year = AsyncMock(
            return_value=LeaveCalendarYearDto(year=2026, segments=[], total_days=0)
        )
        self.service.replace_year = AsyncMock(
            return_value=LeaveCalendarYearDto(year=2026, segments=[], total_days=3)
        )
        self.service.list_years = AsyncMock(
            return_value=LeaveHolidayYearsDto(
                years=[2026], current_year=2026, next_year=2027
            )
        )
        self.service.get_policy = MagicMock(return_value=current_policy())

        self.controller = LeaveCalendarController(self.service, self.database)

        self.patcher = patch("backend.leave.leave_calendar_controller.api_response")
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(self.patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=2)
        self.routes = {
            (route.path, method): route
            for route in self.controller.router.routes
            for method in route.methods
        }

    async def test_reading_a_year_delegates_to_the_service(self):
        response = await self.controller.get_year(2026)

        self.service.get_year.assert_awaited_once_with(self.session, 2026)
        self.assertEqual(response["data"].year, 2026)

    async def test_replacing_a_year_passes_the_segments_through(self):
        payload = LeaveCalendarReplaceRequestDto(
            segments=[
                LeaveHolidaySegmentInputDto(
                    name="Spring Festival",
                    start_date=datetime.date(2026, 2, 17),
                    end_date=datetime.date(2026, 2, 19),
                    is_exchangeable=False,
                )
            ]
        )

        response = await self.controller.replace_year(2026, payload, self.ctx)

        self.service.replace_year.assert_awaited_once_with(
            self.session, 2026, payload.segments
        )
        self.assertEqual(response["data"].total_days, 3)

    async def test_listing_the_entered_years_delegates(self):
        response = await self.controller.list_years()

        self.service.list_years.assert_awaited_once_with(self.session)
        self.assertEqual(response["data"].next_year, 2027)

    async def test_the_policy_route_needs_no_session(self):
        """The constants are in code, so this route reads nothing."""
        response = await self.controller.get_policy()

        self.database.session.assert_not_called()
        self.assertEqual(response["data"].weekend_labels, ["Sunday", "Monday"])

    async def test_an_unset_ceiling_stays_null_rather_than_zero(self):
        """0 would read as "not one hour may be carried over" -- a different
        policy from "no ceiling is in force"."""
        response = await self.controller.get_policy()

        self.assertIsNone(response["data"].max_carryover_hours)
        self.assertIsNone(response["data"].max_overdraft_hours)

    def test_writing_the_calendar_needs_the_leave_admin_permission(self):
        route = self.routes[("/leave/holidays/{year}", "PUT")]

        self.assertEqual(_route_permissions(route), [Permission.LEAVE_ADMIN])

    def test_reading_is_open_to_any_signed_in_employee(self):
        """Company holidays are reference information the whole company needs,
        and the employee-side dialog reads these same routes. Gating them on
        LEAVE_ADMIN would 403 everyone but the admin, or force a duplicate
        endpoint later. Writing is the privileged action."""
        for path, method in (
            ("/leave/holidays/{year}", "GET"),
            ("/leave/holiday-years", "GET"),
            ("/leave/policy", "GET"),
        ):
            with self.subTest(path=path):
                self.assertIsNone(_route_permissions(self.routes[(path, method)]))


if __name__ == "__main__":
    unittest.main()
