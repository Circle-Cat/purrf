import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from backend.common.communication_enums import ContextType, InboxService
from backend.common.exceptions import ConflictError
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.common.permissions import Permission
from backend.common.recruiting_enums import ApplicationStage, JobKind
from tests.backend_test.communication_test.inbox_service_read_test import (
    _ALL,
    _MENTORSHIP_ALIAS,
    _RECRUITING_ALIAS,
    _Fixture,
    _at,
    _email,
    _in,
    _out,
    _thread,
    _user,
    _viewer,
)

_ANALYST = SimpleNamespace(job_id=5, kind=JobKind.EMPLOYMENT, title="Data Analyst")
_DESIGNER = SimpleNamespace(job_id=9, kind=JobKind.EMPLOYMENT, title="Designer")
_MENTEE = SimpleNamespace(job_id=6, kind=JobKind.ACTIVITY, title="Mentee 2026")


def _application(application_id, job, stage, user_id=40):
    return SimpleNamespace(
        application_id=application_id, job_id=job.job_id, user_id=user_id, stage=stage
    )


class _WriteFixture(_Fixture):
    def setUp(self):
        super().setUp()
        self.calls = []
        self.next_message_id = 1000
        self.session.commit = AsyncMock(
            side_effect=lambda: self.calls.append(("commit",))
        )

        archived = _thread(6, ContextType.MENTORSHIP_INBOX, archived_at=_at(20))
        archived.archived_by_user_id = 70
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX),
            _thread(2, ContextType.MENTORSHIP_INBOX),
            _thread(3, ContextType.INQUIRIES_INBOX),
            _thread(4, ContextType.RECRUITING_INBOX),
            _thread(5, ContextType.APPLICATION, 61, user_id=50),
            archived,
            _thread(7, ContextType.ACTIVITY, 8, user_id=32),
            _thread(8, ContextType.MENTORSHIP_INBOX),
            _thread(9, ContextType.APPLICATION, 57, user_id=40),
        ]
        self.messages = {
            1: [
                _in(10, 0, sender="Asker <asker@ext.com>"),
                _out(11, 5),
                _in(12, 9, sender="Asker Two <Second@Ext.com>"),
                _in(13, 12, sender="robot@ext.com", kind="auto_reply"),
            ],
            2: [_out(20, 0, to="pat@ext.com"), _in(21, 5, sender="pat@ext.com")],
            3: [_in(30, 0)],
            4: [_in(40, 0, sender="Sofia <sofia@ext.com>")],
            5: [_out(50, 0, to="bo@ext.com"), _in(51, 5, sender="Bo <bo@ext.com>")],
            6: [_in(60, 0)],
            7: [_in(70, 0, sender="Lin <lin@ext.com>")],
            8: [_out(80, 0, to="Pat <Pat@Ext.com>, x@y.com")],
            9: [_in(90, 0, sender="Sofia <sofia@ext.com>")],
        }
        self.users = [_user(32, "Lin", "Wu"), _user(40, "Sofia", "Ruiz")]
        self.emails = [
            _email(32, "lin@ext.com", True),
            _email(40, "sofia@ext.com", True),
        ]
        self.rounds = [SimpleNamespace(round_id=8, name="2026 Summer")]
        self.jobs = {5: _ANALYST, 6: _MENTEE, 9: _DESIGNER}
        self.jobs_by_application = {61: _ANALYST, 57: _ANALYST, 41: _ANALYST}
        self.applications = []

        self.round_repo.get_by_round_id = AsyncMock(
            side_effect=lambda s, rid: next(
                (r for r in self.rounds if r.round_id == rid), None
            )
        )
        self.application_repo.get_with_job = AsyncMock(
            side_effect=lambda s, aid: next(
                (
                    (a, self.jobs[a.job_id])
                    for a in self.applications
                    if a.application_id == aid
                ),
                None,
            )
        )
        self.conversation = Mock()
        self.conversation.send = AsyncMock(side_effect=self._send)
        self.service = self._build_service()

        patcher = patch(
            "backend.communication.inbox_writes.record_event",
            new=AsyncMock(side_effect=self._record),
        )
        self.record_event = patcher.start()
        self.addCleanup(patcher.stop)

    async def _send(self, session, **kwargs):
        self.calls.append(("send",))
        self.next_message_id += 1
        message = _out(self.next_message_id, 500, to=", ".join(kwargs["to"]))
        self.messages.setdefault(kwargs["thread_id"], []).append(message)
        return SimpleNamespace(
            message_id=message.message_id, thread_id=kwargs["thread_id"]
        )

    async def _record(self, session, **kwargs):
        self.calls.append(("event", kwargs["event_type"]))

    def _thread_of(self, tid):
        return next(t for t in self.threads if t.thread_id == tid)

    def _event_kwargs(self):
        self.record_event.assert_awaited_once()
        return self.record_event.call_args.kwargs

    def _assert_event_then_commit(self, event_type, thread_id, details=None):
        self.assertEqual(self.calls, [("event", event_type), ("commit",)])
        kwargs = self._event_kwargs()
        self.assertEqual(kwargs["subject_type"], INBOX_SUBJECT_TYPE)
        self.assertEqual(kwargs["subject_id"], thread_id)
        self.assertEqual(kwargs["actor_id"], 900)
        if details is not None:
            self.assertEqual(kwargs["details"], details)

    def _assert_nothing_written(self):
        self.session.commit.assert_not_awaited()
        self.record_event.assert_not_awaited()
        self.conversation.send.assert_not_awaited()


class ReplyTest(_WriteFixture):
    async def test_stale_last_seen_message_is_a_conflict(self):
        with self.assertRaises(ConflictError) as caught:
            await self.service.reply(self.session, _viewer(*_ALL), 1, "<p>hi</p>", 12)

        self.assertEqual(caught.exception.code, "THREAD_CHANGED")
        self.assertEqual(
            str(caught.exception),
            "This thread has new messages. Read them before sending.",
        )
        self._assert_nothing_written()

    async def test_reply_sends_from_the_service_alias_to_the_newest_human_sender(self):
        detail = await self.service.reply(
            self.session, _viewer(*_ALL), 1, "<p>hi</p>", 13
        )

        kwargs = self.conversation.send.call_args.kwargs
        self.assertEqual(kwargs["sender_address"], _MENTORSHIP_ALIAS)
        self.assertEqual(kwargs["to"], ["second@ext.com"])
        self.assertEqual(kwargs["subject"], "Re: Subject 1")
        self.assertEqual(kwargs["body"], "<p>hi</p>")
        self.assertEqual(kwargs["thread_id"], 1)
        self.assertEqual(kwargs["context_type"], ContextType.MENTORSHIP_INBOX)
        self.assertIsNone(kwargs["context_id"])
        self.assertEqual(kwargs["sender_user_id"], 900)
        self.assertEqual(self.calls, [("send",), ("commit",)])
        self.record_event.assert_not_awaited()
        self.assertEqual(detail.latest_message_id, self.next_message_id)

    async def test_reply_keeps_an_existing_re_prefix(self):
        self._thread_of(1).subject = "RE: Question"

        await self.service.reply(self.session, _viewer(*_ALL), 1, "b", 13)

        self.assertEqual(
            self.conversation.send.call_args.kwargs["subject"], "RE: Question"
        )

    async def test_thread_without_inbound_replies_to_the_first_recipient(self):
        await self.service.reply(self.session, _viewer(*_ALL), 8, "b", 80)

        self.assertEqual(self.conversation.send.call_args.kwargs["to"], ["pat@ext.com"])

    async def test_recruiting_reply_sends_from_the_recruiting_alias_only(self):
        viewer = _viewer(Permission.RECRUITING_APPLICATION_ADVANCE)

        await self.service.reply(self.session, viewer, 4, "b", 40)

        kwargs = self.conversation.send.call_args.kwargs
        self.assertEqual(kwargs["sender_address"], _RECRUITING_ALIAS)
        self.assertEqual(kwargs["context_type"], ContextType.RECRUITING_INBOX)
        self.assertEqual(kwargs["to"], ["sofia@ext.com"])
        self.assertEqual(self.calls, [("send",), ("commit",)])
        self.record_event.assert_not_awaited()

    async def test_threads_we_started_or_assigned_are_not_found(self):
        for thread_id, last_seen in ((5, 51), (7, 70), (9, 90)):
            with self.assertRaises(ValueError) as caught:
                await self.service.reply(
                    self.session, _viewer(*_ALL), thread_id, "b", last_seen
                )
            self.assertEqual(str(caught.exception), f"thread {thread_id} not found")

        self._assert_nothing_written()

    async def test_no_alias_for_the_service_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            await self.service.reply(self.session, _viewer(*_ALL), 3, "b", 30)

        self.assertEqual(
            str(caught.exception), "This environment has no alias for this inbox"
        )
        self._assert_nothing_written()

    async def test_invisible_thread_is_not_found(self):
        with self.assertRaises(ValueError) as caught:
            await self.service.reply(
                self.session, _viewer(Permission.INQUIRIES_MANAGE), 1, "b", 13
            )

        self.assertEqual(str(caught.exception), "thread 1 not found")
        self._assert_nothing_written()


class ArchiveTest(_WriteFixture):
    async def test_archive_stamps_the_thread(self):
        detail = await self.service.archive(self.session, _viewer(*_ALL), 1)

        thread = self._thread_of(1)
        self.assertIsNotNone(thread.archived_at.tzinfo)
        self.assertEqual(thread.archived_by_user_id, 900)
        self._assert_event_then_commit(InboxEvent.ARCHIVED, 1)
        self.assertTrue(detail.archived)
        self.assertFalse(detail.needs_reply)

    async def test_archiving_an_archived_thread_is_rejected(self):
        with self.assertRaises(ValueError):
            await self.service.archive(self.session, _viewer(*_ALL), 6)

        self._assert_nothing_written()

    async def test_unarchive_clears_both_columns(self):
        detail = await self.service.unarchive(self.session, _viewer(*_ALL), 6)

        thread = self._thread_of(6)
        self.assertIsNone(thread.archived_at)
        self.assertIsNone(thread.archived_by_user_id)
        self._assert_event_then_commit(InboxEvent.UNARCHIVED, 6)
        self.assertFalse(detail.archived)

    async def test_unarchiving_a_live_thread_is_rejected(self):
        with self.assertRaises(ValueError):
            await self.service.unarchive(self.session, _viewer(*_ALL), 1)

        self._assert_nothing_written()

    async def test_archive_of_an_invisible_thread_is_not_found(self):
        with self.assertRaises(ValueError) as caught:
            await self.service.archive(
                self.session, _viewer(Permission.MENTORSHIP_ADMIN_WRITE), 3
            )

        self.assertEqual(str(caught.exception), "thread 3 not found")
        self._assert_nothing_written()


class AssignTest(_WriteFixture):
    async def test_mentorship_thread_is_assigned_to_a_round_and_leaves_the_inbox(
        self,
    ):
        result = await self.service.assign(
            self.session, _viewer(*_ALL), 1, person_id=32, round_id=8
        )

        thread = self._thread_of(1)
        self.assertEqual(
            (thread.user_id, thread.context_type, thread.context_id),
            (32, ContextType.ACTIVITY, 8),
        )
        self._assert_event_then_commit(
            InboxEvent.ASSIGNED, 1, {"userId": 32, "roundId": 8}
        )
        self.assertIsNone(result)
        self.assertNotIn(1, self._ids(await self._list()))
        with self.assertRaises(ValueError) as caught:
            await self.service.get_thread(self.session, _viewer(*_ALL), 1)
        self.assertEqual(str(caught.exception), "thread 1 not found")

    async def test_an_assigned_thread_cannot_be_assigned_again(self):
        with self.assertRaises(ValueError) as caught:
            await self.service.assign(
                self.session, _viewer(*_ALL), 7, person_id=32, round_id=8
            )

        self.assertEqual(str(caught.exception), "thread 7 not found")
        self._assert_nothing_written()

    async def test_missing_round_is_rejected(self):
        with self.assertRaises(ValueError):
            await self.service.assign(
                self.session, _viewer(*_ALL), 1, person_id=32, round_id=99
            )

        self._assert_nothing_written()

    async def test_missing_person_is_rejected(self):
        with self.assertRaises(ValueError):
            await self.service.assign(
                self.session, _viewer(*_ALL), 1, person_id=404, round_id=8
            )

        self._assert_nothing_written()

    async def test_mentorship_thread_cannot_take_an_application(self):
        with self.assertRaisesRegex(ValueError, "assigned to a round"):
            await self.service.assign(
                self.session,
                _viewer(*_ALL),
                1,
                person_id=40,
                round_id=8,
                application_id=57,
            )

        self._assert_nothing_written()

    async def test_inquiries_thread_cannot_be_assigned(self):
        with self.assertRaises(ValueError):
            await self.service.assign(
                self.session, _viewer(*_ALL), 3, person_id=32, round_id=8
            )

        self._assert_nothing_written()

    async def test_tracked_thread_cannot_be_assigned(self):
        with self.assertRaises(ValueError):
            await self.service.assign(
                self.session, _viewer(*_ALL), 2, person_id=32, round_id=8
            )

        self._assert_nothing_written()

    async def test_recruiting_assign_attaches_the_chosen_rejected_application(self):
        self.applications = [
            _application(41, _ANALYST, ApplicationStage.REJECTED),
            _application(57, _ANALYST, ApplicationStage.TECH),
            _application(60, _DESIGNER, ApplicationStage.APPLIED),
        ]
        viewer = _viewer(Permission.RECRUITING_APPLICATION_ADVANCE)

        result = await self.service.assign(
            self.session, viewer, 4, person_id=40, application_id=41
        )

        thread = self._thread_of(4)
        self.assertEqual(
            (thread.user_id, thread.context_type, thread.context_id),
            (40, ContextType.APPLICATION, 41),
        )
        self._assert_event_then_commit(
            InboxEvent.ASSIGNED, 4, {"userId": 40, "applicationId": 41}
        )
        self.assertIsNone(result)
        self.assertNotIn(4, self._ids(await self._list(viewer)))

    async def test_recruiting_assign_needs_an_application(self):
        with self.assertRaisesRegex(ValueError, "assigned to an application"):
            await self.service.assign(self.session, _viewer(*_ALL), 4, person_id=40)

        self._assert_nothing_written()

    async def test_recruiting_thread_cannot_take_a_round(self):
        self.applications = [_application(57, _ANALYST, ApplicationStage.APPLIED)]

        with self.assertRaisesRegex(ValueError, "assigned to an application"):
            await self.service.assign(
                self.session,
                _viewer(*_ALL),
                4,
                person_id=40,
                round_id=8,
                application_id=57,
            )

        self._assert_nothing_written()

    async def test_recruiting_assign_to_someone_elses_application_is_rejected(self):
        self.applications = [
            _application(57, _ANALYST, ApplicationStage.APPLIED, user_id=32)
        ]

        with self.assertRaisesRegex(ValueError, "does not belong to user 40"):
            await self.service.assign(
                self.session, _viewer(*_ALL), 4, person_id=40, application_id=57
            )

        self._assert_nothing_written()

    async def test_recruiting_assign_to_an_activity_application_is_rejected(self):
        self.applications = [_application(62, _MENTEE, ApplicationStage.APPLIED)]

        with self.assertRaisesRegex(ValueError, "Only an employment job"):
            await self.service.assign(
                self.session, _viewer(*_ALL), 4, person_id=40, application_id=62
            )

        self._assert_nothing_written()

    async def test_recruiting_assign_to_a_missing_application_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "application 404 not found"):
            await self.service.assign(
                self.session, _viewer(*_ALL), 4, person_id=40, application_id=404
            )

        self._assert_nothing_written()


class MoveTest(_WriteFixture):
    async def test_move_out_of_sight_returns_none_and_hides_the_thread(self):
        viewer = _viewer(Permission.MENTORSHIP_ADMIN_WRITE)

        result = await self.service.move(
            self.session, viewer, 6, InboxService.INQUIRIES
        )

        thread = self._thread_of(6)
        self.assertEqual(thread.context_type, ContextType.INQUIRIES_INBOX)
        self.assertIsNone(thread.archived_at)
        self.assertIsNone(thread.archived_by_user_id)
        self._assert_event_then_commit(
            InboxEvent.MOVED, 6, {"from": "mentorship", "to": "inquiries"}
        )
        self.assertIsNone(result)
        with self.assertRaises(ValueError) as caught:
            await self.service.get_thread(self.session, viewer, 6)
        self.assertEqual(str(caught.exception), "thread 6 not found")

    async def test_move_into_a_visible_service_returns_the_thread_there(self):
        detail = await self.service.move(
            self.session, _viewer(*_ALL), 1, InboxService.RECRUITING
        )

        self.assertEqual(self._thread_of(1).context_type, ContextType.RECRUITING_INBOX)
        self.assertEqual(detail.service, InboxService.RECRUITING)

    async def test_an_assigned_thread_cannot_move(self):
        with self.assertRaises(ValueError) as caught:
            await self.service.move(
                self.session, _viewer(*_ALL), 7, InboxService.RECRUITING
            )

        self.assertEqual(str(caught.exception), "thread 7 not found")
        self._assert_nothing_written()

    async def test_tracked_thread_cannot_move(self):
        with self.assertRaises(ValueError):
            await self.service.move(
                self.session, _viewer(*_ALL), 2, InboxService.INQUIRIES
            )

        self._assert_nothing_written()

    async def test_move_to_the_same_service_is_rejected(self):
        with self.assertRaises(ValueError):
            await self.service.move(
                self.session, _viewer(*_ALL), 1, InboxService.MENTORSHIP
            )

        self._assert_nothing_written()


if __name__ == "__main__":
    unittest.main()
