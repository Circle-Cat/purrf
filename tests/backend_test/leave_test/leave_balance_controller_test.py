"""Routes and gating for leave balance and ledger queries."""

from http import HTTPStatus
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.api_endpoints import LEAVE_BALANCE_ENDPOINT
from backend.dto.user_context_dto import UserContextDto
from backend.leave.leave_balance_controller import LeaveBalanceController


def _route_permissions(route):
    """The permission list closed over by the authenticate decorator, or None
    for a route that only requires a logged-in user."""
    free_variables = route.endpoint.__code__.co_freevars
    if "permissions" not in free_variables:
        return None
    return route.endpoint.__closure__[free_variables.index("permissions")].cell_contents


class TestLeaveBalanceController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.service = MagicMock()
        self.service.get_leave_balance = AsyncMock(
            return_value={"total_days": 10, "ledger": []}
        )

        self.controller = LeaveBalanceController(self.service, self.database)

        self.patcher = patch("backend.leave.leave_balance_controller.api_response")
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
                "status_code": status_code,
                "success": success,
            }
        )
        self.addCleanup(self.patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=2)
        self.routes = {
            (route.path, method): route
            for route in self.controller.router.routes
            for method in route.methods
        }

    async def test_getting_balance_delegates_to_the_service(self):
        """Verify get_balance uses the user_id from token context and delegates to the balance service with the async session."""
        response = await self.controller.get_balance(self.ctx)

        self.database.session.assert_called_once()
        self.service.get_leave_balance.assert_awaited_once_with(
            self.session, self.ctx.user_id
        )
        self.assertEqual(response["message"], "Leave balance fetched.")
        self.assertEqual(response["data"], {"total_days": 10, "ledger": []})

    def test_reading_balance_is_open_to_any_signed_in_employee(self):
        """Leave balance queries require authentication but no extra LEAVE_ADMIN permission."""
        route = self.routes[(LEAVE_BALANCE_ENDPOINT, "GET")]

        self.assertIsNone(_route_permissions(route))

    async def test_getting_balance_handles_null_response_for_new_employees(self):
        """An uninitialized balance returns None rather than failing or raising
        an error."""
        self.service.get_leave_balance.return_value = None

        response = await self.controller.get_balance(self.ctx)

        self.service.get_leave_balance.assert_awaited_once_with(
            self.session, self.ctx.user_id
        )
        self.assertEqual(response["message"], "Leave balance fetched.")
        self.assertIsNone(response["data"])

    async def test_getting_balance_accepts_non_integer_user_ids(self):
        """String or UUID user IDs attached to the token context pass through without modification."""
        uuid_ctx = UserContextDto(
            sub="s", primary_email="a@b.com", user_id="usr_9988-abc-xyz"
        )

        response = await self.controller.get_balance(uuid_ctx)

        self.service.get_leave_balance.assert_awaited_once_with(
            self.session, "usr_9988-abc-xyz"
        )
        self.assertEqual(response["message"], "Leave balance fetched.")

    async def test_getting_balance_propagates_service_exceptions_and_cleans_up_session(
        self,
    ):
        """Database or service errors propagate upward while ensuring the async session context manager exits properly."""
        self.service.get_leave_balance.side_effect = RuntimeError(
            "Database query failed"
        )

        with self.assertRaises(RuntimeError) as cm:
            await self.controller.get_balance(self.ctx)

        self.assertEqual(str(cm.exception), "Database query failed")
        self.database.session.return_value.__aexit__.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()