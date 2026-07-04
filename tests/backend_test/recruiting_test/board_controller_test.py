import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Response

from backend.dto.board_dto import (
    BlacklistDto,
    ReassignDto,
    RoundChangeDto,
    StageChangeDto,
    SubStatusChangeDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.common.permissions import Permission
from backend.common.recruiting_enums import ApplicationStage
from backend.recruiting.board_controller import BoardController


class TestBoardController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.board_service = MagicMock()
        self.board_service.list_my_jobs = AsyncMock(return_value=[])
        self.board_service.get_board = AsyncMock(return_value={})
        self.board_service.get_application_detail = AsyncMock(return_value={"id": 10})
        self.board_service.change_stage = AsyncMock(return_value={"id": 10})
        self.board_service.set_sub_status = AsyncMock(return_value={"id": 10})
        self.board_service.set_round = AsyncMock(return_value={"id": 10})
        self.board_service.blacklist = AsyncMock(return_value={"id": 10})
        self.board_service.get_resume = AsyncMock(return_value=b"%PDF-1.4 data")

        self.controller = BoardController(self.board_service, self.database)

        self.patcher = patch("backend.recruiting.board_controller.api_response")
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(self.patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=2)

    async def test_list_my_jobs_delegates(self):
        jobs = [{"id": 1}]
        self.board_service.list_my_jobs = AsyncMock(return_value=jobs)
        resp = await self.controller.list_my_jobs(self.ctx)
        self.board_service.list_my_jobs.assert_awaited_once_with(self.session, self.ctx)
        self.assertEqual(resp["data"], jobs)

    async def test_get_board_delegates(self):
        board = {"applied": []}
        self.board_service.get_board = AsyncMock(return_value=board)
        resp = await self.controller.get_board(self.ctx, job_id=7)
        self.board_service.get_board.assert_awaited_once_with(self.session, self.ctx, 7)
        self.assertEqual(resp["data"], board)

    async def test_get_application_detail_delegates(self):
        detail = {"id": 10}
        self.board_service.get_application_detail = AsyncMock(return_value=detail)
        resp = await self.controller.get_application_detail(self.ctx, application_id=10)
        self.board_service.get_application_detail.assert_awaited_once_with(
            self.session, self.ctx, 10
        )
        self.assertEqual(resp["data"], detail)

    async def test_change_stage_delegates(self):
        updated = {"id": 10, "stage": "tech"}
        self.board_service.change_stage = AsyncMock(return_value=updated)
        dto = StageChangeDto(to_stage=ApplicationStage.TECH)

        resp = await self.controller.change_stage(
            self.ctx, application_id=10, stage_data=dto
        )

        self.board_service.change_stage.assert_awaited_once_with(
            self.session, self.ctx, 10, dto
        )
        self.assertEqual(resp["data"], updated)

    async def test_set_sub_status_delegates(self):
        updated = {"id": 10, "sub_status": "in_progress"}
        self.board_service.set_sub_status = AsyncMock(return_value=updated)
        dto = SubStatusChangeDto(sub_status="in_progress")

        resp = await self.controller.set_sub_status(
            self.ctx, application_id=10, sub_status_data=dto
        )

        self.board_service.set_sub_status.assert_awaited_once_with(
            self.session, self.ctx, 10, dto
        )
        self.assertEqual(resp["data"], updated)

    async def test_reassign_delegates(self):
        updated = {"id": 10, "sub_status": "pending"}
        self.board_service.reassign = AsyncMock(return_value=updated)
        dto = ReassignDto(assignee_id=42)

        resp = await self.controller.reassign(
            self.ctx, application_id=10, reassign_data=dto
        )

        self.board_service.reassign.assert_awaited_once_with(
            self.session, self.ctx, 10, dto
        )
        self.assertEqual(resp["data"], updated)

    async def test_set_round_delegates(self):
        updated = {"id": 10, "current_round": 2}
        self.board_service.set_round = AsyncMock(return_value=updated)
        dto = RoundChangeDto(round=2)

        resp = await self.controller.set_round(
            self.ctx, application_id=10, round_data=dto
        )

        self.board_service.set_round.assert_awaited_once_with(
            self.session, self.ctx, 10, dto
        )
        self.assertEqual(resp["data"], updated)

    async def test_blacklist_delegates(self):
        updated = {"id": 10, "stage": "rejected"}
        self.board_service.blacklist = AsyncMock(return_value=updated)
        dto = BlacklistDto(
            user_id=3, application_id=10, reason="Fabricated credentials"
        )

        resp = await self.controller.blacklist(self.ctx, blacklist_data=dto)

        self.board_service.blacklist.assert_awaited_once_with(
            self.session, self.ctx, dto
        )
        self.assertEqual(resp["data"], updated)

    async def test_get_resume_returns_raw_pdf_response(self):
        self.board_service.get_resume = AsyncMock(return_value=b"%PDF-1.4 data")

        resp = await self.controller.get_resume(self.ctx, application_id=10)

        self.board_service.get_resume.assert_awaited_once_with(
            self.session, self.ctx, 10
        )
        self.assertIsInstance(resp, Response)
        self.assertEqual(resp.body, b"%PDF-1.4 data")
        self.assertEqual(resp.media_type, "application/pdf")

    def test_resume_route_is_get_and_plain_authenticated(self):
        routes_by_path = {route.path: route for route in self.controller.router.routes}

        resume_route = routes_by_path[
            "/recruiting/applications/{application_id}/resume"
        ]

        self.assertIn("GET", resume_route.methods)

    # -- route registration: PATCH methods + permission gate --
    #
    # This test suite calls controller methods directly rather than through
    # a FastAPI TestClient (see the other tests above), so `authenticate()`
    # never actually runs here. We can still assert what the route table
    # (path/method) and the `authenticate(permissions=[...])` closure were
    # registered with, which is what enforces the gate at request time.

    def _endpoint_permissions(self, endpoint):
        """Pull the `permissions` list out of an authenticate()-wrapped endpoint."""
        idx = endpoint.__code__.co_freevars.index("permissions")
        return endpoint.__closure__[idx].cell_contents

    def test_decision_routes_are_patch_and_permission_gated(self):
        routes_by_path = {route.path: route for route in self.controller.router.routes}

        stage_route = routes_by_path["/recruiting/applications/{application_id}/stage"]
        sub_status_route = routes_by_path[
            "/recruiting/applications/{application_id}/sub-status"
        ]

        reassign_route = routes_by_path[
            "/recruiting/applications/{application_id}/assignment"
        ]

        self.assertIn("PATCH", stage_route.methods)
        self.assertIn("PATCH", sub_status_route.methods)
        self.assertIn("PATCH", reassign_route.methods)
        self.assertEqual(
            self._endpoint_permissions(stage_route.endpoint),
            [Permission.RECRUITING_APPLICATION_ADVANCE],
        )
        self.assertEqual(
            self._endpoint_permissions(sub_status_route.endpoint),
            [Permission.RECRUITING_APPLICATION_ADVANCE],
        )
        self.assertEqual(
            self._endpoint_permissions(reassign_route.endpoint),
            [Permission.RECRUITING_APPLICATION_ADVANCE],
        )

    def test_blacklist_route_is_post_and_permission_gated(self):
        routes_by_path = {route.path: route for route in self.controller.router.routes}

        blacklist_route = routes_by_path["/recruiting/blacklist"]

        self.assertIn("POST", blacklist_route.methods)
        self.assertEqual(
            self._endpoint_permissions(blacklist_route.endpoint),
            [Permission.RECRUITING_BLACKLIST_WRITE],
        )


if __name__ == "__main__":
    unittest.main()
