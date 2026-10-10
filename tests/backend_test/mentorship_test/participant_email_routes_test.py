import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.common.exceptions import ConflictError, NotFoundError
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.common.permissions import Permission
from backend.dto.email_dto import EmailConversationDto, EmailRefreshDto
from backend.mentorship.mentorship_admin_controller import MentorshipAdminController

_BASE = "/mentorship/admin/rounds/7/participants/3104/emails"


class ParticipantEmailRoutesTest(unittest.TestCase):
    """The five routes, through the real permission decorator."""

    def setUp(self):
        self.emails = MagicMock()
        conversation = EmailConversationDto(threads=[], can_send=True)
        for name in ("get_emails", "send_email", "reply"):
            setattr(self.emails, name, AsyncMock(return_value=conversation))
        self.emails.refresh = AsyncMock(
            return_value=EmailRefreshDto(conversation=conversation, new_replies=1)
        )
        self.emails.attachment = AsyncMock(return_value=(b"%PDF", "cv.pdf"))

    def _client(self, permissions):
        database = MagicMock()
        database.session.return_value.__aenter__.return_value = AsyncMock()
        database.session.return_value.__aexit__.return_value = None
        controller = MentorshipAdminController(
            mentorship_admin_service=MagicMock(),
            matching_run_service=MagicMock(),
            matching_run_read_service=MagicMock(),
            matching_draft_service=MagicMock(),
            mentorship_approval_service=MagicMock(),
            launchdarkly_service=MagicMock(),
            participant_email_service=self.emails,
            database=database,
        )
        app = FastAPI()

        @app.middleware("http")
        async def _inject(request: Request, call_next):
            # Explicit values, never a bare MagicMock: every attribute of one
            # is truthy.
            request.state.user = MagicMock(
                permissions={str(p) for p in permissions},
                user_id=9,
                is_super_admin=False,
                is_active=True,
                is_blocked=False,
                sub="auth0|9",
            )
            return await call_next(request)

        app.include_router(controller.router)
        register_exception_handlers(app)
        return TestClient(app, raise_server_exceptions=False)

    def _reader(self):
        return self._client([Permission.MENTORSHIP_ADMIN_READ])

    def _writer(self):
        return self._client([Permission.MENTORSHIP_ADMIN_WRITE])

    def test_reading_needs_read(self):
        ok = self._reader().get(_BASE)

        self.assertEqual(ok.status_code, HTTPStatus.OK)
        self.assertTrue(ok.json()["data"]["canSend"])
        self.assertEqual(self.emails.get_emails.await_args.args[1:3], (7, 3104))
        self.assertEqual(self._writer().get(_BASE).status_code, HTTPStatus.FORBIDDEN)

    def test_sending_needs_write_and_passes_the_form(self):
        payload = {"to": ["ann@x.com"], "subject": "Hi", "body": "Hello"}

        self.assertEqual(
            self._reader().post(_BASE, json=payload).status_code, HTTPStatus.FORBIDDEN
        )
        response = self._writer().post(_BASE, json=payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            self.emails.send_email.await_args.kwargs,
            {"to": ["ann@x.com"], "subject": "Hi", "body": "Hello"},
        )

    def test_a_bad_form_is_400_before_the_service(self):
        for payload in (
            {"to": [], "subject": "Hi", "body": "x"},
            {"to": ["a@x.com"], "subject": "Hi", "body": "x" * 10_001},
        ):
            with self.subTest(payload=payload):
                response = self._writer().post(_BASE, json=payload)
                self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

        self.emails.send_email.assert_not_awaited()

    def test_reply_passes_thread_and_last_seen_and_a_stale_view_is_409(self):
        url = f"{_BASE}/70/reply"

        ok = self._writer().post(url, json={"body": "Thanks", "lastSeenMessageId": 12})
        self.assertEqual(ok.status_code, HTTPStatus.OK)
        self.assertEqual(
            self.emails.reply.await_args.kwargs,
            {"thread_id": 70, "body": "Thanks", "last_seen_message_id": 12},
        )

        self.emails.reply.side_effect = ConflictError("new mail", code="THREAD_CHANGED")
        stale = self._writer().post(url, json={"body": "Thanks", "lastSeenMessageId": 11})
        self.assertEqual(stale.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(stale.json()["data"], {"code": "THREAD_CHANGED"})

        reader = self._reader().post(url, json={"body": "Thanks", "lastSeenMessageId": 12})
        self.assertEqual(reader.status_code, HTTPStatus.FORBIDDEN)

    def test_refresh_needs_write_and_reports_new_replies(self):
        response = self._writer().post(f"{_BASE}/refresh")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"]["newReplies"], 1)
        self.assertEqual(
            self._reader().post(f"{_BASE}/refresh").status_code, HTTPStatus.FORBIDDEN
        )

    def test_attachment_is_a_read_and_downloads(self):
        url = f"{_BASE}/messages/5/attachments/0"

        response = self._reader().get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, b"%PDF")
        self.assertIn("filename*=UTF-8''cv.pdf", response.headers["content-disposition"])
        self.assertEqual(
            self.emails.attachment.await_args.kwargs, {"message_id": 5, "index": 0}
        )
        self.assertEqual(self._writer().get(url).status_code, HTTPStatus.FORBIDDEN)

    def test_unknown_round_or_person_is_404_and_no_alias_is_400(self):
        self.emails.get_emails.side_effect = NotFoundError(
            "Mentorship round 7 does not exist."
        )
        self.assertEqual(self._reader().get(_BASE).status_code, HTTPStatus.NOT_FOUND)

        self.emails.send_email.side_effect = ValueError(
            "This environment has no address to send these emails from"
        )
        response = self._writer().post(
            _BASE, json={"to": ["a@x.com"], "subject": "Hi", "body": "x"}
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)


if __name__ == "__main__":
    unittest.main()
