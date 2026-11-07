import unittest
from datetime import datetime, timezone
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.common.api_endpoints import (
    GUIDE_PROGRESS_ENDPOINT,
    GUIDES_PROGRESS_ENDPOINT,
)
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.common.onboarding_guide_enums import GuideProgressStatus
from backend.dto.guide_progress_dto import GuideProgressDto
from backend.onboarding_guide.guide_progress_controller import (
    GuideProgressController,
)

USER_ID = 10
UPDATED = datetime(2026, 11, 2, 10, 30, tzinfo=timezone.utc)


class _FakeSession:
    """Stands in for ``database.session()``; yields the same session object."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


class TestGuideProgressController(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.service = MagicMock()
        self.service.list_for_user = AsyncMock(
            return_value=[
                GuideProgressDto(
                    guide_key="first-login",
                    status=GuideProgressStatus.SNOOZED,
                    snooze_count=1,
                    updated_at=UPDATED,
                )
            ]
        )
        self.service.record = AsyncMock(
            return_value=GuideProgressDto(
                guide_key="first-login",
                status=GuideProgressStatus.COMPLETED,
                snooze_count=0,
                updated_at=UPDATED,
            )
        )
        database = MagicMock()
        database.session = lambda: _FakeSession(self.session)
        self.controller = GuideProgressController(self.service, database)

        app = FastAPI()

        @app.middleware("http")
        async def _inject(request: Request, call_next):
            request.state.user = MagicMock(
                permissions=set(),
                user_id=USER_ID,
                is_super_admin=False,
                is_active=True,
                is_blocked=False,
                sub="google-oauth2|1",
                primary_email="a@b.com",
            )
            return await call_next(request)

        app.include_router(self.controller.router)
        register_exception_handlers(app)
        self.client = TestClient(app, raise_server_exceptions=False)

    def _put(self, guide_key, body):
        return self.client.put(
            GUIDE_PROGRESS_ENDPOINT.format(guide_key=guide_key), json=body
        )

    def test_list_progress_reads_the_callers_rows(self):
        response = self.client.get(GUIDES_PROGRESS_ENDPOINT)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.service.list_for_user.assert_awaited_once_with(self.session, USER_ID)
        self.assertEqual(
            response.json()["data"],
            [
                {
                    "guideKey": "first-login",
                    "status": "snoozed",
                    "snoozeCount": 1,
                    "updatedAt": "2026-11-02T10:30:00Z",
                }
            ],
        )

    def test_record_progress_writes_for_the_caller(self):
        response = self._put("first-login", {"status": "completed"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.service.record.assert_awaited_once_with(
            self.session, USER_ID, "first-login", GuideProgressStatus.COMPLETED
        )
        self.assertEqual(response.json()["data"]["status"], "completed")

    def test_each_status_reaches_the_service(self):
        for status in GuideProgressStatus:
            with self.subTest(status=status):
                self.service.record.reset_mock()

                self._put("recruiting-board", {"status": status.value})

                self.assertEqual(self.service.record.await_args.args[3], status)

    def test_a_bad_key_is_a_400(self):
        self.service.record.side_effect = ValueError(
            "Guide key must be 1 to 64 lowercase letters, digits or hyphens."
        )

        response = self._put("Bad_Key", {"status": "completed"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertFalse(response.json()["success"])

    def test_an_unknown_status_is_refused_before_the_service(self):
        """The app's handler turns request validation errors into 400."""
        response = self._put("first-login", {"status": "finished"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.service.record.assert_not_awaited()

    def test_a_missing_status_is_refused_before_the_service(self):
        response = self._put("first-login", {})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.service.record.assert_not_awaited()

    def test_routes_are_login_gated_without_permissions(self):
        routes = {
            (route.path, method): route
            for route in self.controller.router.routes
            for method in route.methods
        }

        for key in [
            (GUIDES_PROGRESS_ENDPOINT, "GET"),
            (GUIDE_PROGRESS_ENDPOINT, "PUT"),
        ]:
            with self.subTest(route=key):
                endpoint = routes[key].endpoint
                free = endpoint.__code__.co_freevars
                self.assertIn("permissions", free)
                self.assertIsNone(
                    endpoint.__closure__[free.index("permissions")].cell_contents
                )


class TestGuideProgressControllerWithoutUser(unittest.TestCase):
    def test_no_user_is_refused(self):
        service = MagicMock()
        service.list_for_user = AsyncMock()
        controller = GuideProgressController(service, MagicMock())
        app = FastAPI()
        app.include_router(controller.router)
        register_exception_handlers(app)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(GUIDES_PROGRESS_ENDPOINT)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        service.list_for_user.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
