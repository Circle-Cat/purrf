import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, Mock

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from backend.common.api_endpoints import (
    GMAIL_FULL_RESYNC_ENDPOINT,
    GMAIL_WATCH_MAINTAIN_ENDPOINT,
)
from backend.common.permissions import Permission
from backend.communication.gmail_sync_controller import GmailSyncController
from backend.dto.user_context_dto import UserContextDto


class _FakeDatabase:
    def __init__(self, session):
        self.session_object = session

    def session(self):
        return self

    async def __aenter__(self):
        return self.session_object

    async def __aexit__(self, *exc_info):
        return False


class GmailSyncControllerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.service = AsyncMock()
        self.service.renew_watch.return_value = {
            "expiration": "2026-10-07T00:00:00+00:00"
        }
        self.service.catch_up.return_value = {
            "threads": 1,
            "newMessages": 2,
            "failed": 0,
        }
        self.logger = MagicMock()
        self.controller = GmailSyncController(
            logger=self.logger,
            gmail_sync_service=self.service,
            database=_FakeDatabase(self.session),
        )
        self.user = UserContextDto(sub="s", primary_email="cron@x.com", user_id=1)

    def _route(self, path):
        return {route.path: route for route in self.controller.router.routes}[path]

    def _permissions(self, path):
        endpoint = self._route(path).endpoint
        idx = endpoint.__code__.co_freevars.index("permissions")
        return endpoint.__closure__[idx].cell_contents

    async def test_maintain_renews_then_catches_up(self):
        order = Mock()
        order.attach_mock(self.service.renew_watch, "renew_watch")
        order.attach_mock(self.service.catch_up, "catch_up")

        response = await self.controller.maintain(current_user=self.user)

        self.assertEqual([c[0] for c in order.mock_calls], ["renew_watch", "catch_up"])
        self.service.renew_watch.assert_awaited_once_with(self.session)
        self.service.catch_up.assert_awaited_once_with(self.session)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn(b'"watch"', response.body)
        self.assertIn(b'"catchUp"', response.body)

    async def test_failed_renewal_still_catches_up_then_propagates(self):
        self.service.renew_watch.side_effect = RuntimeError("watch failed")
        with self.assertRaises(RuntimeError) as raised:
            await self.controller.maintain(current_user=self.user)
        self.assertEqual(str(raised.exception), "watch failed")
        self.service.catch_up.assert_awaited_once_with(self.session)

    async def test_renewal_error_wins_over_a_catch_up_error(self):
        self.service.renew_watch.side_effect = RuntimeError("watch failed")
        self.service.catch_up.side_effect = ValueError("catch-up failed")
        with self.assertRaises(RuntimeError) as raised:
            await self.controller.maintain(current_user=self.user)
        self.assertEqual(str(raised.exception), "watch failed")
        self.logger.exception.assert_called_once()

    async def test_catch_up_failure_propagates(self):
        self.service.catch_up.side_effect = RuntimeError("catch-up failed")
        with self.assertRaises(RuntimeError):
            await self.controller.maintain(current_user=self.user)

    def test_maintain_requires_system_sync(self):
        self.assertIn("POST", self._route(GMAIL_WATCH_MAINTAIN_ENDPOINT).methods)
        self.assertEqual(
            self._permissions(GMAIL_WATCH_MAINTAIN_ENDPOINT), [Permission.SYSTEM_SYNC]
        )

    def test_resync_requires_ops_maintain(self):
        self.assertIn("POST", self._route(GMAIL_FULL_RESYNC_ENDPOINT).methods)
        self.assertEqual(
            self._permissions(GMAIL_FULL_RESYNC_ENDPOINT), [Permission.OPS_MAINTAIN]
        )

    async def test_resync_queues_the_full_resync_without_alerting(self):
        tasks = BackgroundTasks()

        response = await self.controller.resync(
            current_user=self.user, background_tasks=tasks
        )

        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)
        self.service.full_resync.assert_not_awaited()
        self.assertEqual(len(tasks.tasks), 1)
        await tasks()
        self.service.full_resync.assert_awaited_once_with(self.session, alert=False)

    async def test_background_resync_failure_is_logged_not_raised(self):
        self.service.full_resync.side_effect = RuntimeError("db down")
        tasks = BackgroundTasks()
        await self.controller.resync(current_user=self.user, background_tasks=tasks)
        await tasks()
        self.logger.exception.assert_called_once()

    def test_resync_route_answers_202_and_runs_after_the_response(self):
        app = FastAPI()

        @app.middleware("http")
        async def set_user(request, call_next):
            request.state.user = UserContextDto(
                sub="s",
                primary_email="ops@x.com",
                user_id=2,
                permissions=frozenset({Permission.OPS_MAINTAIN}),
            )
            return await call_next(request)

        app.include_router(self.controller.router)
        response = TestClient(app).post(GMAIL_FULL_RESYNC_ENDPOINT)

        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)
        self.service.full_resync.assert_awaited_once_with(self.session, alert=False)

    def test_resync_route_refuses_a_caller_without_ops_maintain(self):
        app = FastAPI()

        @app.middleware("http")
        async def set_user(request, call_next):
            request.state.user = UserContextDto(
                sub="s",
                primary_email="x@x.com",
                user_id=3,
                permissions=frozenset({Permission.SYSTEM_SYNC}),
            )
            return await call_next(request)

        app.include_router(self.controller.router)
        response = TestClient(app).post(GMAIL_FULL_RESYNC_ENDPOINT)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.service.full_resync.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
