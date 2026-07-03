import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.dto.user_context_dto import UserContextDto
from backend.recruiting.blacklist_controller import BlacklistController


class TestBlacklistController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.blacklist_service = MagicMock()
        self.blacklist_service.list_blacklist = AsyncMock(return_value=[])
        self.blacklist_service.unblock = AsyncMock(return_value=None)

        self.controller = BlacklistController(self.blacklist_service, self.database)

        self.patcher = patch("backend.recruiting.blacklist_controller.api_response")
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(self.patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=2)

    async def test_list_blacklist_delegates_with_no_search(self):
        entries = [{"userId": 1}]
        self.blacklist_service.list_blacklist = AsyncMock(return_value=entries)

        resp = await self.controller.list_blacklist(self.ctx)

        self.blacklist_service.list_blacklist.assert_awaited_once_with(
            self.session, None
        )
        self.assertEqual(resp["data"], entries)

    async def test_list_blacklist_passes_search_through(self):
        await self.controller.list_blacklist(self.ctx, search="token")
        self.blacklist_service.list_blacklist.assert_awaited_once_with(
            self.session, "token"
        )

    async def test_unblock_delegates(self):
        resp = await self.controller.unblock(self.ctx, user_id=42)
        self.blacklist_service.unblock.assert_awaited_once_with(self.session, 42)
        self.assertEqual(resp["message"], "User unblocked.")


if __name__ == "__main__":
    unittest.main()
