"""Routes for the admin side of leave."""

import datetime
import unittest
from decimal import Decimal
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common.permissions import Permission
from backend.dto.leave_adjustment_dto import (
    LeaveAdjustmentRequestDto,
    LeaveAdjustmentResultDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.leave.leave_admin_controller import LeaveAdminController


def _route_permissions(route):
    free_variables = route.endpoint.__code__.co_freevars
    if "permissions" not in free_variables:
        return None
    return route.endpoint.__closure__[free_variables.index("permissions")].cell_contents


class TestLeaveAdminController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.service = MagicMock()
        self.service.adjust = AsyncMock(
            return_value=LeaveAdjustmentResultDto(
                user_id=7,
                hours="40.00",
                effective_date=datetime.date(2025, 12, 31),
                note="Carried over from Lattice",
                balance_hours="40.00",
            )
        )
        self.engine = MagicMock()
        self.engine.overview = AsyncMock()
        self.balance_service = MagicMock()
        self.balance_service.list_ledger = AsyncMock()
        self.controller = LeaveAdminController(
            self.service, self.engine, self.balance_service, self.database
        )

        patcher = patch("backend.leave.leave_admin_controller.api_response")
        self.mock_api_response = patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=2)
        self.payload = LeaveAdjustmentRequestDto(
            user_id=7,
            hours=Decimal("40.00"),
            effective_date=datetime.date(2025, 12, 31),
            note="Carried over from Lattice",
        )

    def test_reading_every_balance_needs_the_leave_admin_permission(self):
        """It is the whole company's balances. Nothing else on the leave
        feature is gated, which is exactly why this one has to be."""
        routes = {
            (route.path, method): route
            for route in self.controller.router.routes
            for method in route.methods
        }
        route = routes[("/leave/balances", "GET")]

        self.assertEqual(_route_permissions(route), [Permission.LEAVE_ADMIN])

    async def test_the_overview_comes_from_the_run_itself(self):
        """Not a query of its own: an overview that could disagree with what
        the accrual pays would hide the gap the page exists to show."""
        await self.controller.balances()

        self.engine.overview.assert_awaited_once_with(self.session)

    async def test_the_caller_is_recorded_as_the_author(self):
        """Not taken from the body: whoever signed in is who did it."""
        await self.controller.adjust(self.payload, self.ctx)

        self.service.adjust.assert_awaited_once_with(
            self.session,
            user_id=7,
            hours=Decimal("40.00"),
            effective_date=datetime.date(2025, 12, 31),
            note="Carried over from Lattice",
            author_user_id=2,
        )

    async def test_the_resulting_balance_comes_back(self):
        response = await self.controller.adjust(self.payload, self.ctx)

        self.assertEqual(response["data"].balance_hours, "40.00")

    def test_adjusting_a_balance_needs_the_leave_admin_permission(self):
        routes = {
            (route.path, method): route
            for route in self.controller.router.routes
            for method in route.methods
        }
        route = routes[("/leave/adjustments", "POST")]

        self.assertEqual(_route_permissions(route), [Permission.LEAVE_ADMIN])

    def test_reading_ledger_needs_the_leave_admin_permission(self):
        routes = {
            (route.path, method): route
            for route in self.controller.router.routes
            for method in route.methods
        }
        route = routes[("/leave/ledger", "GET")]

        self.assertEqual(_route_permissions(route), [Permission.LEAVE_ADMIN])

    async def test_ledger_delegates_to_balance_service(self):
        await self.controller.ledger(user_id=7, page=2, page_size=20)

        self.balance_service.list_ledger.assert_awaited_once_with(
            self.session,
            user_id=7,
            page=2,
            page_size=20,
        )

    def _client(self):
        """The router behind a stand-in for the auth middleware, as a leave admin."""
        app = FastAPI()

        @app.middleware("http")
        async def as_leave_admin(request, call_next):
            request.state.user = UserContextDto(
                sub="s",
                primary_email="a@b.com",
                user_id=2,
                permissions=frozenset({Permission.LEAVE_ADMIN}),
            )
            return await call_next(request)

        app.include_router(self.controller.router)
        return TestClient(app)

    def test_ledger_accepts_a_real_user_id(self):
        self.balance_service.list_ledger.return_value = {}

        response = self._client().get("/leave/ledger?userId=7")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.balance_service.list_ledger.assert_awaited_once()

    def test_ledger_refuses_a_user_id_below_one(self):
        # Without the bound an id of 0 read as somebody with no history.
        client = self._client()
        for user_id in ("0", "-5"):
            with self.subTest(user_id=user_id):
                response = client.get(f"/leave/ledger?userId={user_id}")

                self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.balance_service.list_ledger.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
