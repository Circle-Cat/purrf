import unittest
from datetime import datetime, timezone
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, create_autospec

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.common.communication_enums import InboxService
from backend.common.exceptions import ConflictError
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.common.permissions import Permission
from backend.communication.inbox_access import INBOX_GATE
from backend.communication.inbox_controller import (
    InboxController,
    _attachment_disposition,
)
from backend.communication.inbox_service import InboxThreadService
from backend.dto.inbox_dto import (
    AssignOptionsDto,
    InboxCountsDto,
    InboxJobOptionDto,
    InboxListDto,
    InboxQueryDto,
    InboxRoundOptionDto,
    InboxServiceCountDto,
    InboxThreadDetailDto,
    PersonDto,
)
from backend.dto.user_context_dto import UserContextDto

_T0 = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


def _detail(thread_id=31):
    return InboxThreadDetailDto(
        thread_id=thread_id,
        service=InboxService.MENTORSHIP,
        subject="Question",
        last_activity_at=_T0,
        needs_reply=True,
        archived=False,
        unassigned=False,
        no_matching_user=True,
        messages=[],
        latest_message_id=77,
        can_assign=True,
        can_move=True,
        tracked=False,
    )


class InboxControllerTest(unittest.TestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None
        self.service = create_autospec(InboxThreadService, instance=True, spec_set=True)
        self.controller = InboxController(
            inbox_thread_service=self.service, database=self.database
        )

        app = FastAPI()
        register_exception_handlers(app)
        self.user = UserContextDto(
            sub="s",
            primary_email="admin@circlecat.org",
            user_id=5,
            permissions=frozenset({Permission.MENTORSHIP_ADMIN_WRITE}),
        )

        @app.middleware("http")
        async def _inject_user(request: Request, call_next):
            request.state.user = self.user
            return await call_next(request)

        app.include_router(self.controller.router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def _as(self, *permissions):
        self.user = UserContextDto(
            sub="s",
            primary_email="admin@circlecat.org",
            user_id=5,
            permissions=frozenset(permissions),
        )

    # -- route table --

    def _permissions(self, endpoint):
        idx = endpoint.__code__.co_freevars.index("permissions")
        return endpoint.__closure__[idx].cell_contents

    def test_every_route_and_its_gate(self):
        gates = {
            (method, route.path): self._permissions(route.endpoint)
            for route in self.controller.router.routes
            for method in route.methods
        }
        people_gate = [
            Permission.MENTORSHIP_ADMIN_WRITE,
            Permission.RECRUITING_APPLICATION_ADVANCE,
        ]
        expected = {
            ("GET", "/inbox/threads"): INBOX_GATE,
            ("GET", "/inbox/count"): INBOX_GATE,
            ("GET", "/inbox/threads/{thread_id}"): INBOX_GATE,
            ("POST", "/inbox/threads/{thread_id}/reply"): INBOX_GATE,
            ("POST", "/inbox/threads/{thread_id}/archive"): INBOX_GATE,
            ("POST", "/inbox/threads/{thread_id}/unarchive"): INBOX_GATE,
            ("PUT", "/inbox/threads/{thread_id}/assignment"): INBOX_GATE,
            ("DELETE", "/inbox/threads/{thread_id}/assignment"): INBOX_GATE,
            ("POST", "/inbox/threads/{thread_id}/move"): INBOX_GATE,
            ("GET", "/inbox/threads/{thread_id}/assign-options"): INBOX_GATE,
            ("GET", "/inbox/people"): people_gate,
            (
                "GET",
                "/inbox/threads/{thread_id}/messages/{message_id}"
                "/attachments/{attachment_id}",
            ): INBOX_GATE,
        }
        self.assertEqual(gates, expected)

    def test_a_mentorship_reader_is_refused(self):
        self._as(Permission.MENTORSHIP_ADMIN_READ)

        responses = [
            self.client.get("/inbox/threads"),
            self.client.get("/inbox/count"),
            self.client.get("/inbox/people", params={"q": "ann"}),
        ]

        self.assertEqual([r.status_code for r in responses], [403, 403, 403])
        self.service.list_threads.assert_not_called()
        self.service.count_needs_reply.assert_not_called()
        self.service.search_people.assert_not_called()

    def test_an_inquiries_manager_cannot_search_people(self):
        self._as(Permission.INQUIRIES_MANAGE)

        response = self.client.get("/inbox/people", params={"q": "ann"})

        self.assertEqual(response.status_code, 403)

    # -- reads --

    def test_list_reads_camel_case_filters(self):
        self.service.list_threads.return_value = InboxListDto(
            threads=[],
            counts=InboxCountsDto(needs_reply=2, unassigned=1),
            services=[InboxServiceCountDto(key=InboxService.MENTORSHIP, needs_reply=2)],
        )

        response = self.client.get(
            "/inbox/threads",
            params={
                "service": "recruiting",
                "needsReply": "true",
                "unassigned": "false",
                "archived": "true",
                "q": "ann",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"],
            {
                "threads": [],
                "counts": {"needsReply": 2, "unassigned": 1},
                "services": [{"key": "mentorship", "needsReply": 2}],
            },
        )
        session, user, query = self.service.list_threads.await_args.args
        self.assertIs(session, self.session)
        self.assertEqual(user.user_id, 5)
        self.assertEqual(
            query,
            InboxQueryDto(
                service=InboxService.RECRUITING,
                needs_reply=True,
                unassigned=False,
                archived=True,
                q="ann",
            ),
        )

    def test_list_without_filters(self):
        self.service.list_threads.return_value = InboxListDto(
            threads=[], counts=InboxCountsDto(needs_reply=0, unassigned=0), services=[]
        )

        self.client.get("/inbox/threads")

        self.assertEqual(self.service.list_threads.await_args.args[2], InboxQueryDto())

    def test_count(self):
        self.service.count_needs_reply.return_value = 4

        response = self.client.get("/inbox/count")

        self.assertEqual(response.json()["data"], {"needsReply": 4})

    def test_detail(self):
        self.service.get_thread.return_value = _detail()

        response = self.client.get("/inbox/threads/31")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual((data["threadId"], data["latestMessageId"]), (31, 77))
        self.assertEqual(self.service.get_thread.await_args.args[2], 31)

    def test_not_found_is_400(self):
        self.service.get_thread.side_effect = ValueError("thread 31 not found")

        response = self.client.get("/inbox/threads/31")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "thread 31 not found")

    # -- writes --

    def test_reply(self):
        self.service.reply.return_value = _detail()

        response = self.client.post(
            "/inbox/threads/31/reply", json={"body": "<p>Hi</p>", "lastSeenMessageId": 77}
        )

        self.assertEqual(response.status_code, 200)
        args = self.service.reply.await_args.args
        self.assertEqual(args[2:], (31, "<p>Hi</p>", 77))
        self.session.commit.assert_not_called()

    def test_stale_reply_is_409_with_its_code(self):
        self.service.reply.side_effect = ConflictError(
            "This thread has new messages.", code="THREAD_CHANGED"
        )

        response = self.client.post(
            "/inbox/threads/31/reply", json={"body": "Hi", "lastSeenMessageId": 70}
        )

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(response.json()["data"]["code"], "THREAD_CHANGED")

    def test_reply_needs_a_body(self):
        response = self.client.post(
            "/inbox/threads/31/reply", json={"lastSeenMessageId": 70}
        )

        self.assertEqual(response.status_code, 400)
        self.service.reply.assert_not_called()

    def test_archive_and_unarchive(self):
        self.service.archive.return_value = _detail()
        self.service.unarchive.return_value = _detail()

        archived = self.client.post("/inbox/threads/31/archive")
        unarchived = self.client.post("/inbox/threads/32/unarchive")

        self.assertEqual((archived.status_code, unarchived.status_code), (200, 200))
        self.assertEqual(self.service.archive.await_args.args[2], 31)
        self.assertEqual(self.service.unarchive.await_args.args[2], 32)

    def test_assign_to_a_round(self):
        self.service.assign.return_value = _detail()

        response = self.client.put(
            "/inbox/threads/31/assignment", json={"userId": 40, "roundId": 3}
        )

        self.assertEqual(response.status_code, 200)
        call = self.service.assign.await_args
        self.assertEqual(call.args[2:], (31, 40))
        self.assertEqual(call.kwargs, {"round_id": 3, "job_id": None})

    def test_assign_to_a_job(self):
        self.service.assign.return_value = _detail()

        self.client.put("/inbox/threads/31/assignment", json={"userId": 40, "jobId": 9})

        self.assertEqual(
            self.service.assign.await_args.kwargs, {"round_id": None, "job_id": 9}
        )

    def test_unassign(self):
        self.service.unassign.return_value = _detail()

        response = self.client.delete("/inbox/threads/31/assignment")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.unassign.await_args.args[2], 31)

    def test_move(self):
        self.service.move.return_value = _detail()

        response = self.client.post(
            "/inbox/threads/31/move", json={"service": "inquiries"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["threadId"], 31)
        self.assertEqual(
            self.service.move.await_args.args[2:], (31, InboxService.INQUIRIES)
        )

    def test_move_out_of_sight_succeeds_with_no_detail(self):
        self.service.move.return_value = None

        response = self.client.post(
            "/inbox/threads/31/move", json={"service": "inquiries"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIsNone(response.json()["data"])

    def test_move_to_an_unknown_service_is_400(self):
        response = self.client.post("/inbox/threads/31/move", json={"service": "hr"})

        self.assertEqual(response.status_code, 400)
        self.service.move.assert_not_called()

    # -- assign options and people --

    def test_round_options_return_only_rounds(self):
        self.service.assign_options.return_value = AssignOptionsDto(
            rounds=[
                InboxRoundOptionDto(round_id=3, name=None, current=True, registered=False)
            ]
        )

        response = self.client.get(
            "/inbox/threads/31/assign-options", params={"userId": 40}
        )

        self.assertEqual(
            response.json()["data"],
            {"rounds": [{"roundId": 3, "name": None, "current": True, "registered": False}]},
        )
        self.assertEqual(self.service.assign_options.await_args.args[2:], (31, 40))

    def test_job_options_return_only_jobs(self):
        self.service.assign_options.return_value = AssignOptionsDto(
            jobs=[
                InboxJobOptionDto(
                    job_id=9,
                    title="Analyst",
                    application_id=11,
                    application_status="rejected",
                    fallback=True,
                )
            ]
        )

        response = self.client.get(
            "/inbox/threads/31/assign-options", params={"userId": 40}
        )

        self.assertEqual(
            response.json()["data"],
            {
                "jobs": [
                    {
                        "jobId": 9,
                        "title": "Analyst",
                        "applicationId": 11,
                        "applicationStatus": "rejected",
                        "fallback": True,
                    }
                ]
            },
        )

    def test_assign_options_need_a_person(self):
        response = self.client.get("/inbox/threads/31/assign-options")

        self.assertEqual(response.status_code, 400)
        self.service.assign_options.assert_not_called()

    def test_people(self):
        self._as(Permission.RECRUITING_APPLICATION_ADVANCE)
        self.service.search_people.return_value = [
            PersonDto(user_id=7, name="Ann Lee", email=None)
        ]

        response = self.client.get("/inbox/people", params={"q": "ann"})

        self.assertEqual(
            response.json()["data"], [{"userId": 7, "name": "Ann Lee", "email": None}]
        )
        self.assertEqual(self.service.search_people.await_args.args[1], "ann")

    # -- attachments --

    def test_attachment_download(self):
        self.service.download_attachment.return_value = (b"%PDF", '../\u7b80\u5386 "v2".pdf')

        response = self.client.get("/inbox/threads/31/messages/77/attachments/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"%PDF")
        self.assertEqual(response.headers["content-type"], "application/octet-stream")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        disposition = response.headers["content-disposition"]
        self.assertNotIn("/", disposition.split("filename*=")[0])
        self.assertIn("filename*=UTF-8''", disposition)
        self.assertEqual(
            self.service.download_attachment.await_args.args[2:], (31, 77, 1)
        )

    def test_attachment_of_another_thread_is_400(self):
        self.service.download_attachment.side_effect = ValueError("attachment not found")

        response = self.client.get("/inbox/threads/31/messages/77/attachments/9")

        self.assertEqual(response.status_code, 400)


class AttachmentDispositionTest(unittest.TestCase):
    def test_quotes_slashes_and_non_ascii(self):
        self.assertEqual(
            _attachment_disposition('../\u7b80\u5386 "v2".pdf'),
            "attachment; filename=\"__ v2.pdf\"; "
            "filename*=UTF-8''%E7%AE%80%E5%8E%86%20v2.pdf",
        )

    def test_backslashes_and_control_characters(self):
        self.assertEqual(
            _attachment_disposition("C:\\tmp\\a\r\nb\x00.txt"),
            "attachment; filename=\"C:tmpab.txt\"; filename*=UTF-8''C%3Atmpab.txt",
        )

    def test_plain_name_is_unchanged(self):
        self.assertEqual(
            _attachment_disposition("resume.pdf"),
            "attachment; filename=\"resume.pdf\"; filename*=UTF-8''resume.pdf",
        )

    def test_name_left_empty_falls_back(self):
        self.assertEqual(
            _attachment_disposition('/"\\'),
            "attachment; filename=\"attachment\"; filename*=UTF-8''attachment",
        )


if __name__ == "__main__":
    unittest.main()
