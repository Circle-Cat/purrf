import unittest
from datetime import datetime, timezone
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.admin.block_controller import BlockController
from backend.common.api_endpoints import (
    ADMIN_USER_ADMINS_ENDPOINT,
    BLOCK_PREFLIGHT_ENDPOINT,
    BLOCK_REQUEST_DECIDE_ENDPOINT,
    BLOCK_REQUEST_REASSIGN_ENDPOINT,
    BLOCK_REQUESTS_ENDPOINT,
)
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.common.permissions import Permission
from backend.dto.block_dto import (
    BlockPreflightDto,
    BlockRequestDto,
    ReviewerOptionDto,
)

CALLER = 1
TARGET = 7
REVIEWER = 9
REQUEST_ID = 3


class _FakeSession:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


def _request_dto(reviewer_id=REVIEWER):
    return BlockRequestDto(
        id=REQUEST_ID,
        target_user_id=TARGET,
        target_name="T Arget",
        raised_by=CALLER,
        raised_by_name="C Aller",
        raised_from="recruiting_board",
        raised_at=datetime.now(timezone.utc),
        reason="second no-show",
        reviewer_id=reviewer_id,
        reviewer_name="R Eviewer",
        status="pending",
    )


class TestBlockController(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.service.preflight = AsyncMock(
            return_value=BlockPreflightDto(application_count=2, interview_times=[])
        )
        self.service.raise_request = AsyncMock(return_value=_request_dto())
        self.service.reassign = AsyncMock(return_value=_request_dto())
        self.service.decide = AsyncMock(return_value=_request_dto())
        self.service.list_pending_for_reviewer = AsyncMock(return_value=[])
        self.service.list_user_admins = AsyncMock(return_value=[])

    def _client(self, *, permissions, user_id=CALLER):
        app = FastAPI()
        database = MagicMock()
        database.session = lambda: _FakeSession()
        controller = BlockController(self.service, database)

        @app.middleware("http")
        async def _inject(request: Request, call_next):
            # Explicit booleans, never a bare MagicMock: every attribute of one
            # is truthy, which has previously turned a gate into a blanket 403.
            request.state.user = MagicMock(
                permissions={str(p) for p in permissions},
                user_id=user_id,
                is_super_admin=False,
                is_active=True,
                is_blocked=False,
                sub="google-oauth2|1",
            )
            return await call_next(request)

        app.include_router(controller.router)
        register_exception_handlers(app)
        return TestClient(app, raise_server_exceptions=False)

    # -- the gates ----------------------------------------------------------

    def test_preflight_open_to_all_three_roles(self):
        for permission in (
            Permission.USER_ADMIN,
            Permission.RECRUITING_APPLICATION_ADVANCE,
            Permission.RECRUITING_INTERVIEW_EVALUATE,
        ):
            with self.subTest(permission=permission):
                client = self._client(permissions=[permission])

                resp = client.get(BLOCK_PREFLIGHT_ENDPOINT.format(user_id=TARGET))

                self.assertEqual(resp.status_code, HTTPStatus.OK)

    def test_preflight_is_closed_to_everyone_else(self):
        client = self._client(permissions=[Permission.PERMISSION_MANAGE])

        resp = client.get(BLOCK_PREFLIGHT_ENDPOINT.format(user_id=TARGET))

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_user_admin_cannot_raise_a_request(self):
        """Raising is bound to standing on the domain page that holds the
        evidence, not to holding the console permission."""
        client = self._client(permissions=[Permission.USER_ADMIN])

        resp = client.post(
            f"{BLOCK_REQUESTS_ENDPOINT}?raised_from=recruiting_board",
            json={"userId": TARGET, "reason": "r", "reviewerId": REVIEWER},
        )

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)
        self.service.raise_request.assert_not_awaited()

    def test_recruiter_cannot_decide(self):
        client = self._client(permissions=[Permission.RECRUITING_INTERVIEW_EVALUATE])

        resp = client.post(
            BLOCK_REQUEST_DECIDE_ENDPOINT.format(request_id=REQUEST_ID),
            json={"approved": True},
        )

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)
        self.service.decide.assert_not_awaited()

    def test_user_admin_cannot_reassign(self):
        """Reassigning redirects a question you asked, so it sits with the
        raiser's permissions, not the reviewer's."""
        client = self._client(permissions=[Permission.USER_ADMIN])

        resp = client.post(
            BLOCK_REQUEST_REASSIGN_ENDPOINT.format(request_id=REQUEST_ID),
            json={"reviewerId": REVIEWER},
        )

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_recruiter_cannot_read_the_pending_queue(self):
        client = self._client(permissions=[Permission.RECRUITING_APPLICATION_ADVANCE])

        resp = client.get(BLOCK_REQUESTS_ENDPOINT)

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_user_admin_cannot_read_the_reviewer_dropdown(self):
        client = self._client(permissions=[Permission.USER_ADMIN])

        resp = client.get(ADMIN_USER_ADMINS_ENDPOINT)

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    # -- delegation ---------------------------------------------------------

    def test_raise_passes_the_actor_and_the_page_it_came_from(self):
        client = self._client(permissions=[Permission.RECRUITING_INTERVIEW_EVALUATE])

        resp = client.post(
            f"{BLOCK_REQUESTS_ENDPOINT}?raised_from=recruiting_interviews",
            json={"userId": TARGET, "reason": "second no-show", "reviewerId": REVIEWER},
        )

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.service.raise_request.await_args.kwargs
        self.assertEqual(kwargs["actor_id"], CALLER)
        self.assertEqual(kwargs["user_id"], TARGET)
        self.assertEqual(kwargs["reviewer_id"], REVIEWER)
        self.assertEqual(kwargs["raised_from"], "recruiting_interviews")

    def test_raise_rejects_a_blank_reason(self):
        client = self._client(permissions=[Permission.RECRUITING_INTERVIEW_EVALUATE])

        resp = client.post(
            f"{BLOCK_REQUESTS_ENDPOINT}?raised_from=recruiting_board",
            json={"userId": TARGET, "reason": "   ", "reviewerId": REVIEWER},
        )

        self.assertEqual(resp.status_code, HTTPStatus.BAD_REQUEST)
        self.service.raise_request.assert_not_awaited()

    def test_pending_list_is_scoped_to_the_caller(self):
        """Scoped, not filtered: the caller's own id is the only input, so
        there is no parameter anyone could widen."""
        client = self._client(permissions=[Permission.USER_ADMIN], user_id=REVIEWER)

        resp = client.get(BLOCK_REQUESTS_ENDPOINT)

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(
            self.service.list_pending_for_reviewer.await_args.args[1], REVIEWER
        )

    def test_decide_passes_the_verdict_and_the_actor(self):
        client = self._client(permissions=[Permission.USER_ADMIN], user_id=REVIEWER)

        resp = client.post(
            BLOCK_REQUEST_DECIDE_ENDPOINT.format(request_id=REQUEST_ID),
            json={"approved": False, "note": "not enough"},
        )

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.service.decide.await_args.kwargs
        self.assertEqual(kwargs["actor_id"], REVIEWER)
        self.assertEqual(kwargs["request_id"], REQUEST_ID)
        self.assertIs(kwargs["approved"], False)
        self.assertEqual(kwargs["note"], "not enough")

    def test_reassign_passes_the_new_reviewer(self):
        client = self._client(permissions=[Permission.RECRUITING_APPLICATION_ADVANCE])

        resp = client.post(
            BLOCK_REQUEST_REASSIGN_ENDPOINT.format(request_id=REQUEST_ID),
            json={"reviewerId": REVIEWER},
        )

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        kwargs = self.service.reassign.await_args.kwargs
        self.assertEqual(kwargs["actor_id"], CALLER)
        self.assertEqual(kwargs["reviewer_id"], REVIEWER)

    def test_user_admins_dropdown_delegates_to_the_holder_lookup(self):
        """The dead-letter path this scoping exists to prevent -- naming a
        reviewer who can never sign in -- is closed inside that lookup, which
        already excludes blocked accounts. Nothing here may work around it."""
        self.service.list_user_admins = AsyncMock(
            return_value=[ReviewerOptionDto(user_id=REVIEWER, name="R Eviewer")]
        )
        client = self._client(permissions=[Permission.RECRUITING_INTERVIEW_EVALUATE])

        resp = client.get(ADMIN_USER_ADMINS_ENDPOINT)

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        self.assertEqual(
            [row["userId"] for row in resp.json()["data"]], [REVIEWER]
        )

    # -- error mapping ------------------------------------------------------

    def test_deciding_someone_elses_request_is_a_403(self):
        self.service.decide = AsyncMock(side_effect=PermissionError("not yours"))
        client = self._client(permissions=[Permission.USER_ADMIN])

        resp = client.post(
            BLOCK_REQUEST_DECIDE_ENDPOINT.format(request_id=REQUEST_ID),
            json={"approved": True},
        )

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_reassigning_a_request_you_did_not_raise_is_a_403(self):
        self.service.reassign = AsyncMock(side_effect=PermissionError("not yours"))
        client = self._client(permissions=[Permission.RECRUITING_APPLICATION_ADVANCE])

        resp = client.post(
            BLOCK_REQUEST_REASSIGN_ENDPOINT.format(request_id=REQUEST_ID),
            json={"reviewerId": REVIEWER},
        )

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)

    def test_a_second_pending_request_is_a_400(self):
        self.service.raise_request = AsyncMock(
            side_effect=ValueError("already awaiting a decision")
        )
        client = self._client(permissions=[Permission.RECRUITING_INTERVIEW_EVALUATE])

        resp = client.post(
            f"{BLOCK_REQUESTS_ENDPOINT}?raised_from=recruiting_board",
            json={"userId": TARGET, "reason": "r", "reviewerId": REVIEWER},
        )

        self.assertEqual(resp.status_code, HTTPStatus.BAD_REQUEST)


if __name__ == "__main__":
    unittest.main()
