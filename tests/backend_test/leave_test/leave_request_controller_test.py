"""Routes for filing and deciding leave requests."""

import datetime
import unittest
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.approval.approval_service import APPROVAL_CHECKS_FAILED
from backend.common.api_endpoints import (
    LEAVE_REQUEST_DECISION_ENDPOINT,
    LEAVE_REQUEST_WITHDRAW_ENDPOINT,
)
from backend.common.exceptions import ConflictError
from backend.common.fast_api_error_handler import register_exception_handlers
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
            self.session, 501, 10, approve=True, comment=None
        )

    async def test_the_reason_for_a_decision_is_passed_through(self):
        """Required to reject: the employee is told why."""
        await self.controller.decide(
            501, LeaveDecisionDto(approve=False, comment="No cover."), self.ctx
        )

        self.service.decide.assert_awaited_once_with(
            self.session, 501, 10, approve=False, comment="No cover."
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
        self.service.standing = AsyncMock(
            return_value=SimpleNamespace(
                is_covered=True, available=None, pending=None, used=None
            )
        )

        await self.controller.coverage(self.ctx)

        self.service.standing.assert_awaited_once_with(self.session, 10)

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


class _FakeSession:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


class TestLeaveRequestRoutesOverHttp(unittest.TestCase):
    """What a page sees when the approval flow refuses."""

    def setUp(self):
        self.service = MagicMock()
        self.service.decide = AsyncMock(return_value=None)
        self.service.withdraw = AsyncMock(return_value=None)
        app = FastAPI()
        database = MagicMock()
        database.session = lambda: _FakeSession()
        controller = LeaveRequestController(self.service, database)

        @app.middleware("http")
        async def _inject(request: Request, call_next):
            request.state.user = MagicMock(
                permissions=set(),
                user_id=10,
                is_super_admin=False,
                is_active=True,
                is_blocked=False,
                sub="google-oauth2|1",
                primary_email="a@b.com",
            )
            return await call_next(request)

        app.include_router(controller.router)
        register_exception_handlers(app)
        self.client = TestClient(app, raise_server_exceptions=False)

    def _decide(self, body):
        return self.client.post(
            LEAVE_REQUEST_DECISION_ENDPOINT.format(request_id=501), json=body
        )

    def test_the_comment_in_the_body_reaches_the_service(self):
        response = self._decide({"approve": False, "comment": "No cover."})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        args = self.service.decide.await_args
        self.assertEqual(args.args[1:], (501, 10))
        self.assertEqual(args.kwargs, {"approve": False, "comment": "No cover."})

    def test_a_decision_without_a_comment_sends_none(self):
        self._decide({"approve": True})

        self.assertIsNone(self.service.decide.await_args.kwargs["comment"])

    def test_deciding_something_already_decided_is_a_409(self):
        self.service.decide.side_effect = ConflictError(
            "Request 501 is already approved."
        )

        response = self._decide({"approve": True})

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(response.json()["message"], "Request 501 is already approved.")

    def test_an_approval_that_no_longer_holds_is_a_409_with_its_code(self):
        """The code is how a page tells this apart from somebody else having
        decided it first."""
        self.service.decide.side_effect = ConflictError(
            "This leave started on 2026-08-13.", code=APPROVAL_CHECKS_FAILED
        )

        response = self._decide({"approve": True})

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(response.json()["data"], {"code": APPROVAL_CHECKS_FAILED})

    def test_somebody_other_than_the_approver_is_a_403(self):
        self.service.decide.side_effect = PermissionError(
            "Only the named reviewer may decide this request."
        )

        response = self._decide({"approve": True})

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_rejecting_without_a_reason_is_a_400(self):
        self.service.decide.side_effect = ValueError(
            "Give a reason for rejecting the request."
        )

        response = self._decide({"approve": False})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_withdrawing_a_decided_request_is_a_409(self):
        self.service.withdraw.side_effect = ConflictError(
            "Request 501 is already approved."
        )

        response = self.client.post(
            LEAVE_REQUEST_WITHDRAW_ENDPOINT.format(request_id=501)
        )

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)

    def test_withdrawing_somebody_elses_request_is_a_403(self):
        self.service.withdraw.side_effect = PermissionError(
            "Only the person who raised this can withdraw it."
        )

        response = self.client.post(
            LEAVE_REQUEST_WITHDRAW_ENDPOINT.format(request_id=501)
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
