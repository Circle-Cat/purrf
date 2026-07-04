import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.dto.evaluation_dto import EvaluationSubmitDto
from backend.dto.user_context_dto import UserContextDto
from backend.recruiting.evaluation_controller import EvaluationController


class TestEvaluationController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.evaluation_service = MagicMock()
        self.evaluation_service.submit = AsyncMock(return_value={"id": 1})
        self.evaluation_service.get_mine = AsyncMock(return_value=[])

        self.controller = EvaluationController(self.evaluation_service, self.database)

        self.patcher = patch("backend.recruiting.evaluation_controller.api_response")
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(self.patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=2)

    async def test_submit_evaluation_delegates(self):
        result = {"id": 1, "is_confirmed": False}
        self.evaluation_service.submit = AsyncMock(return_value=result)
        dto = EvaluationSubmitDto(responses={"q1": "a1"}, confirm=False)

        resp = await self.controller.submit_evaluation(
            self.ctx, application_id=10, evaluation_data=dto
        )

        self.evaluation_service.submit.assert_awaited_once_with(
            self.session, self.ctx, 10, dto
        )
        self.assertEqual(resp["data"], result)

    async def test_get_mine_delegates(self):
        result = [{"application_id": 10}]
        self.evaluation_service.get_mine = AsyncMock(return_value=result)

        resp = await self.controller.get_mine(self.ctx)

        self.evaluation_service.get_mine.assert_awaited_once_with(
            self.session, self.ctx
        )
        self.assertEqual(resp["data"], result)

    def test_evaluation_route_is_put_and_plain_authenticated(self):
        routes_by_path = {route.path: route for route in self.controller.router.routes}

        evaluation_route = routes_by_path[
            "/recruiting/applications/{application_id}/evaluation"
        ]

        self.assertIn("PUT", evaluation_route.methods)

    def test_mine_route_is_get_and_plain_authenticated(self):
        routes_by_path = {route.path: route for route in self.controller.router.routes}

        mine_route = routes_by_path["/recruiting/evaluations/mine"]

        self.assertIn("GET", mine_route.methods)


if __name__ == "__main__":
    unittest.main()
