import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.dto.user_context_dto import UserContextDto
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


if __name__ == "__main__":
    unittest.main()
