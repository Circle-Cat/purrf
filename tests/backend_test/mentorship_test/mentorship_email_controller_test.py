import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.common.exceptions import ConflictError
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.common.permissions import Permission
from backend.dto.mentorship_email_dto import (
    EmailNotifiedDto,
    EmailPersonSendDto,
    EmailScheduledStageDto,
    EmailSendDto,
    KitDraftDto,
    NotificationMarkResultDto,
    NotificationMarkSkipDto,
)
from backend.mentorship.mentorship_email_controller import MentorshipEmailController

BASE = "/mentorship/admin/email-sends"
CONFIRM_BODY = {"sendAt": "2026-10-08T13:00:00Z", "previewToken": "t"}
MARK = "/api/mentorship/admin/rounds/7/notifications/mark"
MARK_BODY = {"userIds": [11, 12], "stage": "admission", "body": "  Sent on Teams  "}


def _dto(**kw) -> EmailSendDto:
    fields = dict(
        send_id=1,
        round_id=1,
        stage="match_result",
        kit_draft_id=4400,
        kit_draft_subject="Your match",
        kit_tag_name="purrf-send-1",
        status="draft",
        failure_code=None,
        sender_address="mentorship@example.org",
        kit_broadcast_id=None,
        error_message=None,
        send_at=None,
        created_at=None,
        counts={},
        resume_needed=False,
    )
    fields.update(kw)
    return EmailSendDto(**fields)


class TestMentorshipEmailController(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.prepare_service = MagicMock()
        self.prepare_service.run = AsyncMock()
        self.mark_service = MagicMock()
        self.ld = MagicMock()
        self.ld.is_kit_email_enabled.return_value = True
        database = MagicMock()
        database.session.return_value.__aenter__.return_value = AsyncMock()
        database.session.return_value.__aexit__.return_value = None
        self.controller = MentorshipEmailController(
            mentorship_email_service=self.service,
            mentorship_email_prepare_service=self.prepare_service,
            notification_mark_service=self.mark_service,
            launchdarkly_service=self.ld,
            database=database,
        )
        self.client = self._client([
            Permission.MENTORSHIP_ADMIN_READ,
            Permission.MENTORSHIP_ADMIN_WRITE,
        ])

    def _client(self, permissions):
        app = FastAPI()

        @app.middleware("http")
        async def _inject(request: Request, call_next):
            request.state.user = MagicMock(
                permissions={str(p) for p in permissions},
                user_id=9,
                is_super_admin=False,
                is_active=True,
                is_blocked=False,
                sub="auth0|9",
            )
            return await call_next(request)

        app.include_router(self.controller.router, prefix="/api")
        register_exception_handlers(app)
        return TestClient(app, raise_server_exceptions=False)

    def test_create_returns_201_without_background(self):
        self.service.create_send = AsyncMock(return_value=_dto(send_id=5))
        resp = self.client.post(
            f"/api{BASE}",
            json={
                "roundId": 1,
                "stage": "match_result",
                "kitDraftId": 4400,
                "userIds": [1, 2],
            },
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["data"]["sendId"], 5)
        self.prepare_service.run.assert_not_awaited()
        self.assertEqual(self.service.create_send.await_args.kwargs["created_by"], 9)
        self.assertEqual(self.service.create_send.await_args.args[1].kit_draft_id, 4400)
        self.assertEqual(resp.json()["data"]["kitDraftSubject"], "Your match")
        self.assertNotIn("kitEditUrl", resp.json()["data"])

    def test_confirm_returns_202_and_starts_prepare(self):
        self.service.confirm = AsyncMock(
            return_value=_dto(send_id=5, status="preparing")
        )
        resp = self.client.post(f"/api{BASE}/5/confirm", json=CONFIRM_BODY)
        self.assertEqual(resp.status_code, 202)
        self.prepare_service.run.assert_awaited_once_with(5)

    def test_kit_drafts_are_listed(self):
        self.service.list_drafts = AsyncMock(
            return_value=[KitDraftDto(id=4400, subject="Your match", created_at=None)]
        )
        resp = self.client.get("/api/mentorship/admin/kit-drafts")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["data"],
            [{"id": 4400, "subject": "Your match", "createdAt": None, "problem": None}],
        )

    def test_notified_returns_stages_and_resumes_each_stuck_send(self):
        self.service.list_notified = AsyncMock(
            return_value=(
                [
                    EmailNotifiedDto(
                        user_id=3,
                        stages=["admission", "match_result"],
                        scheduled=[
                            EmailScheduledStageDto(
                                stage="midterm_reminder",
                                send_at=datetime(
                                    2026, 10, 12, 16, 0, tzinfo=timezone.utc
                                ),
                            )
                        ],
                        manual=["onboarding_reminder"],
                    )
                ],
                [1, 3],
            )
        )
        resp = self.client.get(f"/api{BASE}/notified?roundId=7")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["data"],
            [
                {
                    "userId": 3,
                    "stages": ["admission", "match_result"],
                    "scheduled": [
                        {"stage": "midterm_reminder", "sendAt": "2026-10-12T16:00:00Z"}
                    ],
                    "manual": ["onboarding_reminder"],
                }
            ],
        )
        self.assertEqual(self.service.list_notified.await_args.args[1], 7)
        self.assertEqual(
            [c.args for c in self.prepare_service.run.await_args_list], [(1,), (3,)]
        )

    def test_person_sends_are_listed_for_the_round_and_person(self):
        self.service.list_person_sends = AsyncMock(
            return_value=[
                EmailPersonSendDto(
                    send_id=14,
                    stage="match_result",
                    subject="Your match",
                    delivered=False,
                    reason="Not handed to Kit: unsubscribed",
                    at=datetime(2026, 10, 12, 16, 0, tzinfo=timezone.utc),
                )
            ]
        )
        resp = self.client.get(f"/api{BASE}/person?roundId=7&userId=42")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["data"],
            [
                {
                    "sendId": 14,
                    "stage": "match_result",
                    "subject": "Your match",
                    "delivered": False,
                    "reason": "Not handed to Kit: unsubscribed",
                    "at": "2026-10-12T16:00:00Z",
                }
            ],
        )
        self.assertEqual(self.service.list_person_sends.await_args.args[1:], (7, 42))

    def test_person_sends_need_a_round_and_a_person(self):
        self.service.list_person_sends = AsyncMock()
        for query in ("roundId=7", "userId=42"):
            resp = self.client.get(f"/api{BASE}/person?{query}")
            self.assertEqual(resp.status_code, 400, query)
        self.service.list_person_sends.assert_not_awaited()

    def test_notified_needs_a_round(self):
        self.service.list_notified = AsyncMock()
        resp = self.client.get(f"/api{BASE}/notified")
        self.assertEqual(resp.status_code, 400)
        self.service.list_notified.assert_not_awaited()

    def test_removed_routes_are_gone(self):
        for method, path in [
            ("get", "/api/mentorship/admin/kit-templates"),
            ("get", f"/api{BASE}?round_id=1"),
            ("get", f"/api{BASE}/5"),
            ("post", f"/api{BASE}/5/retry"),
        ]:
            resp = getattr(self.client, method)(path)
            self.assertIn(resp.status_code, (404, 405), path)

    def test_flag_off_returns_404(self):
        self.ld.is_kit_email_enabled.return_value = False
        resp = self.client.get("/api/mentorship/admin/kit-drafts")
        self.assertEqual(resp.status_code, 404)
        self.service.list_drafts.assert_not_called()
        resp = self.client.get(f"/api{BASE}/notified?roundId=7")
        self.assertEqual(resp.status_code, 404)
        self.service.list_notified.assert_not_called()
        resp = self.client.get(f"/api{BASE}/person?roundId=7&userId=42")
        self.assertEqual(resp.status_code, 404)
        self.service.list_person_sends.assert_not_called()

    def test_conflict_maps_to_409(self):
        self.service.confirm = AsyncMock(
            side_effect=ConflictError("changed", code="content_changed")
        )
        resp = self.client.post(f"/api{BASE}/5/confirm", json=CONFIRM_BODY)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["data"], {"code": "content_changed"})
        self.prepare_service.run.assert_not_awaited()

    def test_confirm_rejects_send_at_without_offset(self):
        self.service.confirm = AsyncMock()
        resp = self.client.post(
            f"/api{BASE}/5/confirm",
            json={"sendAt": "2026-10-08T13:00:00", "previewToken": "t"},
        )
        self.assertEqual(resp.status_code, 400)
        self.service.confirm.assert_not_awaited()

    def test_value_error_maps_to_400(self):
        self.service.confirm = AsyncMock(side_effect=ValueError("send_at too soon"))
        resp = self.client.post(f"/api{BASE}/5/confirm", json=CONFIRM_BODY)
        self.assertEqual(resp.status_code, 400)

    def test_writing_needs_write_permission(self):
        client = self._client([Permission.MENTORSHIP_ADMIN_READ])
        resp = client.post(f"/api{BASE}/5/cancel")
        self.assertEqual(resp.status_code, 403)

    def test_mark_marks_by_the_caller_and_returns_who(self):
        self.mark_service.mark = AsyncMock(
            return_value=NotificationMarkResultDto(
                marked=[12],
                skipped=[
                    NotificationMarkSkipDto(user_id=11, reason="already_notified")
                ],
            )
        )
        resp = self.client.post(MARK, json=MARK_BODY)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["data"],
            {"marked": [12], "skipped": [{"userId": 11, "reason": "already_notified"}]},
        )
        kwargs = self.mark_service.mark.await_args.kwargs
        self.assertEqual(kwargs["round_id"], 7)
        self.assertEqual(kwargs["user_ids"], [11, 12])
        self.assertEqual(kwargs["stage"], "admission")
        self.assertEqual(kwargs["body"], "Sent on Teams")
        self.assertEqual(kwargs["actor_id"], 9)

    def test_mark_needs_write(self):
        self.mark_service.mark = AsyncMock()
        client = self._client([Permission.MENTORSHIP_ADMIN_READ])

        resp = client.post(MARK, json=MARK_BODY)

        self.assertEqual(resp.status_code, 403)
        self.mark_service.mark.assert_not_awaited()

    def test_mark_is_404_while_the_flag_is_off(self):
        self.ld.is_kit_email_enabled.return_value = False
        self.mark_service.mark = AsyncMock()

        resp = self.client.post(MARK, json=MARK_BODY)

        self.assertEqual(resp.status_code, 404)
        self.mark_service.mark.assert_not_awaited()

    def test_mark_refuses_a_bad_body(self):
        self.mark_service.mark = AsyncMock()
        for body in (
            {**MARK_BODY, "body": "   "},
            {**MARK_BODY, "body": "x" * 5001},
            {**MARK_BODY, "userIds": []},
            {**MARK_BODY, "userIds": list(range(1, 502))},
            {**MARK_BODY, "stage": "pizza_party"},
        ):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(MARK, json=body).status_code, 400)
        self.mark_service.mark.assert_not_awaited()

    def test_mark_outside_a_round_in_progress_is_409(self):
        self.mark_service.mark = AsyncMock(
            side_effect=ConflictError(
                "Notifications can only be marked while the round is in progress.",
                code="round_not_in_progress",
            )
        )
        resp = self.client.post(MARK, json=MARK_BODY)

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["data"], {"code": "round_not_in_progress"})
        self.assertEqual(
            resp.json()["message"],
            "Notifications can only be marked while the round is in progress.",
        )


if __name__ == "__main__":
    unittest.main()
