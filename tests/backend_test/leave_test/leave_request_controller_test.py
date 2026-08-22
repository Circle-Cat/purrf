"""Routes for filing and deciding leave requests."""

import datetime
import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.leave_enums import LeaveRequestType
from backend.dto.leave_request_dto import LeaveDecisionDto, LeaveRequestSubmitDto
from backend.dto.user_context_dto import UserContextDto
from backend.leave.leave_request_controller import LeaveRequestController


def _route_permissions(route):
    free_variables = route.endpoint.__code__.co_freevars
    if "permissions" not in free_variables:
        return None
    return route.endpoint.__closure__[free_variables.index("permissions")].cell_contents


class TestLeaveRequestController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.service = MagicMock()
        self.service.submit = AsyncMock(return_value=MagicMock())
        self.service.withdraw = AsyncMock(return_value=MagicMock())
        self.service.decide = AsyncMock(return_value=MagicMock())
        self.service.list_own = AsyncMock(return_value=[])
        self.service.list_for_approver = AsyncMock(return_value=[])
        self.controller = LeaveRequestController(self.service, self.database)

        patcher = patch("backend.leave.leave_request_controller.api_response")
        self.mock_api_response = patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=10)
        self.routes = {
            (route.path, method): route
            for route in self.controller.router.routes
            for method in route.methods
        }

    async def test_a_request_is_filed_for_whoever_is_signed_in(self):
        """Never for a user id in the body: that would let anybody file leave
        against somebody else's balance."""
        payload = LeaveRequestSubmitDto(
            type=LeaveRequestType.PAID,
            start_date=datetime.date(2026, 8, 13),
            end_date=datetime.date(2026, 8, 15),
            reason="Holiday",
        )

        await self.controller.submit(payload, self.ctx)

        self.service.submit.assert_awaited_once_with(
            self.session,
            user_id=10,
            request_type=LeaveRequestType.PAID,
            start_date=datetime.date(2026, 8, 13),
            end_date=datetime.date(2026, 8, 15),
            start_time=None,
            end_time=None,
            reason="Holiday",
        )

    async def test_withdrawing_names_the_caller_as_the_owner(self):
        await self.controller.withdraw(501, self.ctx)

        self.service.withdraw.assert_awaited_once_with(self.session, 501, 10)

    async def test_deciding_names_the_caller_as_the_approver(self):
        await self.controller.decide(501, LeaveDecisionDto(approve=True), self.ctx)

        self.service.decide.assert_awaited_once_with(
            self.session, 501, 10, approve=True
        )

    async def test_your_own_list_is_your_own(self):
        await self.controller.list_own(self.ctx)

        self.service.list_own.assert_awaited_once_with(self.session, 10)

    async def test_the_queue_is_the_callers_queue(self):
        await self.controller.list_approvals(self.ctx)

        self.service.list_for_approver.assert_awaited_once_with(self.session, 10)

    async def test_coverage_answers_for_the_caller_and_nobody_else(self):
        """No identity in the path or the query: a user id there would let
        anybody read somebody else's standing."""
        self.service.coverage = AsyncMock(return_value=True)

        await self.controller.coverage(self.ctx)

        self.service.coverage.assert_awaited_once_with(self.session, 10)

    def test_every_route_is_open_to_any_signed_in_employee(self):
        """Leave is not an administered feature: everybody files their own and
        managers decide for their own reports. Who may do what is decided by
        ownership inside the service, not by a permission -- a permission
        would have to be granted to every employee, which is the same as not
        having one."""
        for path, method in (
            ("/leave/me", "GET"),
            ("/leave/requests", "POST"),
            ("/leave/requests", "GET"),
            ("/leave/requests/approvals", "GET"),
            ("/leave/requests/{request_id}/withdraw", "POST"),
            ("/leave/requests/{request_id}/decision", "POST"),
        ):
            with self.subTest(path=path, method=method):
                self.assertIsNone(_route_permissions(self.routes[(path, method)]))


if __name__ == "__main__":
    unittest.main()
