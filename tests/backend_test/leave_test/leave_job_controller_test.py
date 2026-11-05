"""The two scheduled leave endpoints a CronJob calls."""

import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.permissions import Permission
from backend.leave.leave_job_controller import LeaveJobController


def _route_permissions(route):
    free_variables = route.endpoint.__code__.co_freevars
    if "permissions" not in free_variables:
        return None
    return route.endpoint.__closure__[free_variables.index("permissions")].cell_contents


class TestLeaveJobController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.service = MagicMock()
        self.service.run_weekly_accrual = AsyncMock(return_value={"paid": 3})
        self.service.run_annual_close = AsyncMock(return_value={"settled": 3})
        self.controller = LeaveJobController(self.service, self.database)

        patcher = patch("backend.leave.leave_job_controller.api_response")
        self.mock_api_response = patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(patcher.stop)

        self.routes = {
            (route.path, method): route
            for route in self.controller.router.routes
            for method in route.methods
        }

    async def test_the_weekly_run_reports_what_it_did(self):
        """The report is the only place the skipped people are named, so it has
        to reach the caller and the logs rather than being dropped."""
        response = await self.controller.run_weekly_accrual()

        self.service.run_weekly_accrual.assert_awaited_once_with(self.session)
        self.assertEqual(response["data"], {"paid": 3})

    async def test_the_annual_run_reports_what_it_did(self):
        response = await self.controller.run_annual_close()

        self.service.run_annual_close.assert_awaited_once_with(self.session)
        self.assertEqual(response["data"], {"settled": 3})

    def test_both_jobs_are_posts_reserved_for_the_scheduler(self):
        """These write to everybody's ledger. Nobody signing in should be able
        to trigger a pay-out, whatever else they hold."""
        for path in ("/leave/jobs/weekly-accrual", "/leave/jobs/annual-close"):
            with self.subTest(path=path):
                route = self.routes[(path, "POST")]
                self.assertEqual(
                    _route_permissions(route),
                    [Permission.SYSTEM_BACKFILL_SCHEDULED],
                )

    def test_neither_job_answers_a_get(self):
        self.assertNotIn(("/leave/jobs/weekly-accrual", "GET"), self.routes)
        self.assertNotIn(("/leave/jobs/annual-close", "GET"), self.routes)


if __name__ == "__main__":
    unittest.main()
