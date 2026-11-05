import unittest
from datetime import date
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.dto.user_context_dto import UserContextDto
from backend.recruiting.audit_controller import AuditController


class TestAuditController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.audit_service = MagicMock()
        self.audit_service.get_overview = AsyncMock(
            return_value={"openPositionsCount": 0}
        )

        self.controller = AuditController(self.audit_service, self.database)

        self.patcher = patch("backend.recruiting.audit_controller.api_response")
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(self.patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=2)

    async def test_get_overview_delegates_with_job_ids(self):
        resp = await self.controller.get_overview(
            self.ctx,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            job_ids=[1, 2],
        )

        self.audit_service.get_overview.assert_awaited_once_with(
            self.session, date(2026, 6, 1), date(2026, 6, 30), [1, 2]
        )
        self.assertEqual(resp["data"], {"openPositionsCount": 0})

    async def test_get_overview_defaults_job_ids_to_empty_list(self):
        await self.controller.get_overview(
            self.ctx, start_date=date(2026, 6, 1), end_date=date(2026, 6, 30)
        )

        self.audit_service.get_overview.assert_awaited_once_with(
            self.session, date(2026, 6, 1), date(2026, 6, 30), []
        )

    def test_overview_route_is_get_and_permission_gated(self):
        from backend.common.permissions import Permission

        routes_by_path = {route.path: route for route in self.controller.router.routes}
        route = routes_by_path["/recruiting/audit/overview"]

        self.assertIn("GET", route.methods)

        idx = route.endpoint.__code__.co_freevars.index("permissions")
        permissions = route.endpoint.__closure__[idx].cell_contents
        self.assertEqual(permissions, [Permission.RECRUITING_AUDIT_READ])


if __name__ == "__main__":
    unittest.main()
