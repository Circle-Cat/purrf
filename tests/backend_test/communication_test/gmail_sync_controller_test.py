import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock

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
        self.service.maintain.return_value = {"watch": {}, "catchUp": {}}
        self.controller = GmailSyncController(
            gmail_maintenance_service=self.service,
            database=_FakeDatabase(self.session),
        )
        self.user = UserContextDto(sub="s", primary_email="cron@x.com", user_id=1)

    def _route(self, path):
        return {route.path: route for route in self.controller.router.routes}[path]

    def _permissions(self, path):
        endpoint = self._route(path).endpoint
        idx = endpoint.__code__.co_freevars.index("permissions")
        return endpoint.__closure__[idx].cell_contents

    def _app_as(self, permissions):
        app = FastAPI()

        @app.middleware("http")
        async def set_user(request, call_next):
            request.state.user = UserContextDto(
                sub="s",
                primary_email="ops@x.com",
                user_id=2,
                permissions=frozenset(permissions),
            )
            return await call_next(request)

        app.include_router(self.controller.router)
        return TestClient(app)

    async def test_maintain_wraps_the_service_result(self):
        response = await self.controller.maintain(current_user=self.user)

        self.service.maintain.assert_awaited_once_with(self.session)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn(b'"watch"', response.body)
        self.assertIn(b'"catchUp"', response.body)

    async def test_maintain_failure_propagates(self):
        self.service.maintain.side_effect = RuntimeError("watch failed")

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

    async def test_resync_queues_the_manual_resync(self):
        tasks = BackgroundTasks()

        response = await self.controller.resync(
            current_user=self.user, background_tasks=tasks
        )

        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)
        self.service.run_manual_full_resync.assert_not_awaited()
        self.assertEqual(len(tasks.tasks), 1)
        await tasks()
        self.service.run_manual_full_resync.assert_awaited_once_with()

    def test_resync_route_answers_202_and_runs_after_the_response(self):
        response = self._app_as({Permission.OPS_MAINTAIN}).post(
            GMAIL_FULL_RESYNC_ENDPOINT
        )

        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)
        self.service.run_manual_full_resync.assert_awaited_once_with()

    def test_resync_route_refuses_a_caller_without_ops_maintain(self):
        response = self._app_as({Permission.SYSTEM_SYNC}).post(
            GMAIL_FULL_RESYNC_ENDPOINT
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.service.run_manual_full_resync.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
