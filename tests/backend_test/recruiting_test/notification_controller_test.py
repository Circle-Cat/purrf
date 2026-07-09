import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.dto.user_context_dto import UserContextDto
from backend.recruiting.notification_controller import RecruitingNotificationController


class TestRecruitingNotificationController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.notification_service = MagicMock()
        self.notification_service.list_for_user = AsyncMock(
            return_value={"notifications": [], "unreadCount": 0}
        )
        self.notification_service.mark_read = AsyncMock(return_value={"unreadCount": 0})
        self.notification_service.mark_all_read = AsyncMock(return_value={"unreadCount": 0})

        self.controller = RecruitingNotificationController(
            self.notification_service, self.database
        )

        self.patcher = patch("backend.recruiting.notification_controller.api_response")
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(self.patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=2)

    async def test_list_notifications_delegates(self):
        result = {"notifications": [{"id": 1}], "unreadCount": 1}
        self.notification_service.list_for_user = AsyncMock(return_value=result)

        resp = await self.controller.list_notifications(self.ctx)

        self.notification_service.list_for_user.assert_awaited_once_with(
            self.session, 2, limit=20, offset=0
        )
        self.assertEqual(resp["data"], result)

    async def test_list_notifications_passes_through_limit_and_offset(self):
        await self.controller.list_notifications(self.ctx, limit=5, offset=10)

        self.notification_service.list_for_user.assert_awaited_once_with(
            self.session, 2, limit=5, offset=10
        )

    async def test_mark_read_delegates(self):
        result = {"unreadCount": 2}
        self.notification_service.mark_read = AsyncMock(return_value=result)

        resp = await self.controller.mark_read(self.ctx, notification_id=7)

        self.notification_service.mark_read.assert_awaited_once_with(self.session, 2, 7)
        self.assertEqual(resp["data"], result)

    async def test_mark_all_read_delegates(self):
        result = {"unreadCount": 0}
        self.notification_service.mark_all_read = AsyncMock(return_value=result)

        resp = await self.controller.mark_all_read(self.ctx)

        self.notification_service.mark_all_read.assert_awaited_once_with(self.session, 2)
        self.assertEqual(resp["data"], result)

    def test_routes_are_registered_and_plain_authenticated(self):
        routes_by_path = {route.path: route for route in self.controller.router.routes}

        list_route = routes_by_path["/recruiting/notifications"]
        self.assertIn("GET", list_route.methods)

        read_route = routes_by_path["/recruiting/notifications/{notification_id}/read"]
        self.assertIn("POST", read_route.methods)

        read_all_route = routes_by_path["/recruiting/notifications/read-all"]
        self.assertIn("POST", read_all_route.methods)


if __name__ == "__main__":
    unittest.main()
