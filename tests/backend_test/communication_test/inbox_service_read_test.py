import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType, InboxService
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.common.permissions import Permission
from backend.common.recruiting_enums import JobKind
from backend.communication.inbox_aliases import InboxAliases
from backend.communication.inbox_service import InboxThreadService
from backend.communication.thread_service import ThreadServiceResolver
from backend.dto.inbox_dto import InboxQueryDto
from backend.dto.user_context_dto import UserContextDto

_T0 = datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc)
_MENTORSHIP_ALIAS = "mentorship-test@circlecat.org"
_RECRUITING_ALIAS = "recruiting-test@circlecat.org"


def _at(minutes):
    return _T0 + timedelta(minutes=minutes)


def _in(mid, minutes, sender="Asker <asker@ext.com>", kind="human", **kw):
    return SimpleNamespace(
        message_id=mid,
        direction="inbound",
        from_address=sender,
        to_addresses=_MENTORSHIP_ALIAS,
        gmail_internal_date=_at(minutes),
        # Stored shortly after Gmail received it, unless the test says when.
        created_at=_at(kw.get("stored", minutes + 1)),
        inbound_kind=kind,
        snippet=kw.get("snippet", f"in {mid}"),
        body_html=kw.get("body_html", f"<p>in {mid}</p>"),
        body_text=kw.get("body_text", f"in {mid}"),
        attachments=kw.get("attachments"),
        sent_by_user_id=None,
        failed_recipients=kw.get("failed_recipients"),
    )


def _out(mid, minutes, to="Asker <asker@ext.com>", sent_by=None):
    return SimpleNamespace(
        message_id=mid,
        direction="outbound",
        from_address=_MENTORSHIP_ALIAS,
        to_addresses=to,
        gmail_internal_date=None,
        created_at=_at(minutes),
        inbound_kind=None,
        snippet=f"out {mid}",
        body_html=f"<p>out {mid}</p>",
        body_text=None,
        attachments=None,
        sent_by_user_id=sent_by,
        failed_recipients=None,
    )


def _thread(tid, context_type, context_id=None, user_id=None, subject=None, **kw):
    return SimpleNamespace(
        thread_id=tid,
        context_type=context_type,
        context_id=context_id,
        user_id=user_id,
        subject=subject or f"Subject {tid}",
        archived_at=kw.get("archived_at"),
        created_at=kw.get("created_at", _at(-1000)),
    )


def _user(user_id, first, last, preferred=None):
    return SimpleNamespace(
        user_id=user_id,
        first_name=first,
        last_name=last,
        preferred_name=preferred,
        is_blocked=False,
    )


def _email(user_id, email, is_primary):
    return SimpleNamespace(user_id=user_id, email=email, is_primary=is_primary)


def _viewer(*permissions):
    return UserContextDto(
        sub="v",
        primary_email="viewer@circlecat.org",
        user_id=900,
        permissions=frozenset(permissions),
    )


_ALL = (
    Permission.MENTORSHIP_ADMIN_WRITE,
    Permission.RECRUITING_APPLICATION_ADVANCE,
    Permission.INQUIRIES_MANAGE,
)


class _Fixture(unittest.IsolatedAsyncioTestCase):
    """Repositories backed by in-memory lists the tests fill in."""

    def setUp(self):
        self.session = Mock()
        self.threads = []
        self.messages = {}
        self.users = []
        self.emails = []
        self.jobs_by_application = {}
        self.rounds = []
        self.moves = {}

        self.thread_repo = Mock()
        self.thread_repo.list_by_context_types = AsyncMock(
            side_effect=lambda s, types: [
                t for t in self.threads if t.context_type in types
            ]
        )
        self.thread_repo.get = AsyncMock(
            side_effect=lambda s, tid: next(
                (t for t in self.threads if t.thread_id == tid), None
            )
        )
        self.message_repo = Mock()
        self.message_repo.list_by_threads = AsyncMock(
            side_effect=lambda s, ids: {i: list(self.messages.get(i, [])) for i in ids}
        )
        self.message_repo.list_by_thread = AsyncMock(
            side_effect=lambda s, tid: list(self.messages.get(tid, []))
        )
        self.email_repo = Mock()
        self.email_repo.list_by_emails = AsyncMock(
            side_effect=lambda s, emails: [e for e in self.emails if e.email in emails]
        )
        self.user_repo = Mock()
        self.user_repo.get_all_by_ids = AsyncMock(
            side_effect=lambda s, ids: [u for u in self.users if u.user_id in ids]
        )
        self.job_repo = Mock()
        self.job_repo.get_by_application_ids = AsyncMock(
            side_effect=lambda s, ids: {
                i: self.jobs_by_application[i]
                for i in ids
                if i in self.jobs_by_application
            }
        )
        self.job_repo.get_by_application_id = AsyncMock(
            side_effect=lambda s, i: self.jobs_by_application.get(i)
        )
        self.round_repo = Mock()
        self.round_repo.get_all_rounds = AsyncMock(side_effect=lambda s: self.rounds)
        self.event_repo = Mock()
        self.event_repo.latest_by_subjects = AsyncMock(
            side_effect=lambda s, subject_type, event_type, ids: {
                i: self.moves[i] for i in ids if i in self.moves
            }
        )
        self.application_repo = Mock()
        self.conversation = SimpleNamespace()
        self.gmail = Mock()
        self.participant_repo = Mock()
        self.rounds_service = Mock()
        self.service = self._build_service()

    def _build_service(self):
        return InboxThreadService(
            thread_repository=self.thread_repo,
            message_repository=self.message_repo,
            user_emails_repository=self.email_repo,
            users_repository=self.user_repo,
            job_repository=self.job_repo,
            application_repository=self.application_repo,
            round_repository=self.round_repo,
            event_repository=self.event_repo,
            thread_service_resolver=ThreadServiceResolver(job_repository=self.job_repo),
            conversation_service=self.conversation,
            aliases=InboxAliases(
                mentorship=_MENTORSHIP_ALIAS, recruiting=_RECRUITING_ALIAS
            ),
            gmail_client=self.gmail,
            round_participants_repository=self.participant_repo,
            rounds_service=self.rounds_service,
        )

    async def _list(self, viewer=None, **query):
        return await self.service.list_threads(
            self.session, viewer or _viewer(*_ALL), InboxQueryDto(**query)
        )

    @staticmethod
    def _ids(result):
        return [row.thread_id for row in result.threads]


class VisibilityTest(_Fixture):
    def setUp(self):
        super().setUp()
        employment = SimpleNamespace(
            kind=JobKind.EMPLOYMENT,
            title="Data Analyst",
            pipeline_config={"owners": [77]},
        )
        activity = SimpleNamespace(kind=JobKind.ACTIVITY, title="Mentee 2026")
        self.jobs_by_application = {57: employment, 61: activity}
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX),
            _thread(2, ContextType.RECRUITING_INBOX),
            _thread(3, ContextType.INQUIRIES_INBOX),
            _thread(4, ContextType.APPLICATION, 57, user_id=30),
            _thread(5, ContextType.APPLICATION, 61, user_id=31),
            _thread(6, ContextType.ACTIVITY, 8, user_id=32),
        ]
        self.messages = {t.thread_id: [_in(t.thread_id * 10, 0)] for t in self.threads}

    async def test_inquiries_only_sees_only_inquiries(self):
        result = await self._list(_viewer(Permission.INQUIRIES_MANAGE))

        self.assertEqual(self._ids(result), [3])
        self.assertEqual([s.key for s in result.services], [InboxService.INQUIRIES])

    async def test_advance_only_sees_only_the_recruiting_inbox(self):
        result = await self._list(_viewer(Permission.RECRUITING_APPLICATION_ADVANCE))

        self.assertEqual(self._ids(result), [2])

    async def test_mentorship_sees_only_the_mentorship_inbox(self):
        result = await self._list(_viewer(Permission.MENTORSHIP_ADMIN_WRITE))

        self.assertEqual(self._ids(result), [1])

    async def test_threads_we_started_or_assigned_are_not_listed_or_counted(self):
        viewer = _viewer(*_ALL)

        result = await self._list(viewer)

        self.assertEqual(sorted(self._ids(result)), [1, 2, 3])
        self.assertEqual(result.counts.needs_reply, 3)
        self.assertEqual([s.needs_reply for s in result.services], [1, 1, 1])
        self.assertEqual(await self.service.count_needs_reply(self.session, viewer), 3)

    async def test_threads_we_started_or_assigned_are_not_found(self):
        for thread_id in (4, 5, 6):
            with self.assertRaises(ValueError) as caught:
                await self.service.get_thread(self.session, _viewer(*_ALL), thread_id)
            self.assertEqual(str(caught.exception), f"thread {thread_id} not found")

        self.message_repo.list_by_thread.assert_not_awaited()

    async def test_invisible_and_missing_raise_the_same_error(self):
        viewer = _viewer(Permission.MENTORSHIP_ADMIN_WRITE)

        with self.assertRaises(ValueError) as invisible:
            await self.service.get_thread(self.session, viewer, 3)
        with self.assertRaises(ValueError) as missing:
            await self.service.get_thread(self.session, viewer, 999)

        self.assertEqual(str(invisible.exception), "thread 3 not found")
        self.assertEqual(str(missing.exception), "thread 999 not found")
        self.message_repo.list_by_thread.assert_not_awaited()

    async def test_no_permission_lists_nothing_without_reading(self):
        result = await self._list(_viewer(Permission.MENTORSHIP_ADMIN_READ))

        self.assertEqual(result.threads, [])
        self.assertEqual(result.services, [])
        self.thread_repo.list_by_context_types.assert_not_awaited()

    async def test_one_query_each_for_messages_and_emails_and_none_for_jobs(self):
        await self._list()

        self.message_repo.list_by_threads.assert_awaited_once()
        self.job_repo.get_by_application_ids.assert_not_awaited()
        self.job_repo.get_by_application_id.assert_not_awaited()
        self.round_repo.get_all_rounds.assert_not_awaited()
        self.email_repo.list_by_emails.assert_awaited_once()
        self.user_repo.get_all_by_ids.assert_awaited_once()


class PersonMatchingTest(_Fixture):
    async def test_display_name_address_matches_case_insensitively(self):
        self.threads = [_thread(1, ContextType.MENTORSHIP_INBOX)]
        self.messages = {1: [_in(10, 0, sender='"Wang" <W.Xiao@Example.com>')]}
        self.emails = [_email(41, "w.xiao@example.com", is_primary=False)]
        self.users = [_user(41, "Xiao", "Wang", preferred="Sofia")]

        row = (await self._list()).threads[0]

        self.assertEqual(row.sender, "w.xiao@example.com")
        self.assertEqual((row.person.user_id, row.person.name), (41, "Sofia"))
        self.assertEqual(row.matched_by, "alternative")
        self.assertFalse(row.no_matching_user)
        self.email_repo.list_by_emails.assert_awaited_once_with(
            self.session, ["w.xiao@example.com"]
        )

    async def test_all_senders_of_a_page_are_matched_in_one_call(self):
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX),
            _thread(2, ContextType.INQUIRIES_INBOX),
        ]
        self.messages = {
            1: [_in(10, 0, sender="a@ext.com")],
            2: [_in(20, 1, sender="B@Ext.com")],
        }
        self.emails = [_email(41, "a@ext.com", is_primary=True)]
        self.users = [_user(41, "Ann", "Lee")]

        rows = {r.thread_id: r for r in (await self._list()).threads}

        self.email_repo.list_by_emails.assert_awaited_once()
        self.assertEqual(
            sorted(self.email_repo.list_by_emails.await_args.args[1]),
            ["a@ext.com", "b@ext.com"],
        )
        self.assertEqual(rows[1].matched_by, "primary")
        self.assertIsNone(rows[2].person)
        self.assertTrue(rows[2].no_matching_user)

    async def test_sender_falls_back_to_first_outbound_recipient(self):
        self.threads = [_thread(1, ContextType.MENTORSHIP_INBOX)]
        self.messages = {
            1: [
                _out(10, 0, to='"Pat" <Pat@Ext.com>, other@ext.com'),
                _in(11, 5, kind="auto_reply"),
            ]
        }

        row = (await self._list()).threads[0]

        self.assertEqual(row.sender, "pat@ext.com")

    async def test_recruiting_person_is_named_by_legal_name(self):
        self.threads = [_thread(1, ContextType.RECRUITING_INBOX)]
        self.messages = {1: [_in(10, 0, sender="bo@ext.com")]}
        self.emails = [_email(50, "bo@ext.com", is_primary=True)]
        self.users = [_user(50, "Bo", "Chen", "Bobby")]

        row = (await self._list()).threads[0]

        self.assertEqual(row.person.name, "Bo Chen")


class SearchTest(_Fixture):
    def setUp(self):
        super().setUp()
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX, subject="Summer 2026 question"),
            _thread(2, ContextType.MENTORSHIP_INBOX, subject="Hello"),
            _thread(3, ContextType.MENTORSHIP_INBOX, subject="Other"),
        ]
        self.messages = {
            1: [_in(10, 0, sender="x@ext.com")],
            2: [_in(20, 1, sender="y@ext.com")],
            3: [_in(30, 2, sender="Maple.Z@Ext.com")],
        }
        self.emails = [
            _email(1555, "x@ext.com", True),
            _email(155, "y@ext.com", True),
        ]
        self.users = [_user(1555, "Ann", "Lee"), _user(155, "Rina", "Ota")]

    async def test_digits_match_only_the_exact_user_id(self):
        self.assertEqual(self._ids(await self._list(q="155")), [2])
        self.assertEqual(self._ids(await self._list(q="#1555")), [1])

    async def test_digits_never_match_the_subject(self):
        self.assertEqual(self._ids(await self._list(q="2026")), [])

    async def test_text_matches_name_address_and_subject_ignoring_case(self):
        self.assertEqual(self._ids(await self._list(q="SUMMER")), [1])
        self.assertEqual(self._ids(await self._list(q="rina")), [2])
        self.assertEqual(self._ids(await self._list(q="maple.z@")), [3])

    async def test_counts_are_unaffected_by_q(self):
        full = await self._list()
        searched = await self._list(q="rina")

        self.assertEqual(searched.counts, full.counts)
        self.assertEqual(searched.counts.needs_reply, 3)
        self.assertEqual(searched.services, full.services)


class FlagsAndOrderTest(_Fixture):
    async def test_needs_reply_first_by_latest_human_inbound_then_activity(self):
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX),
            _thread(2, ContextType.MENTORSHIP_INBOX),
            _thread(3, ContextType.MENTORSHIP_INBOX),
            _thread(4, ContextType.MENTORSHIP_INBOX),
        ]
        self.messages = {
            # needs reply, human inbound at 10, auto-reply later at 90
            1: [_in(10, 10), _in(11, 90, kind="auto_reply")],
            # needs reply, human inbound at 20
            2: [_in(20, 20)],
            # answered, last activity 100
            3: [_in(30, 5), _out(31, 100)],
            # answered, last activity 50
            4: [_in(40, 1), _out(41, 50)],
        }

        result = await self._list()

        self.assertEqual(self._ids(result), [2, 1, 3, 4])
        self.assertEqual(result.threads[1].machine_tag, "auto_reply")
        self.assertEqual(result.threads[1].last_activity_at, _at(90))
        self.assertEqual(result.threads[1].snippet, "in 11")

    async def test_filters_and_counts(self):
        archived_at = _at(50)
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX),
            _thread(2, ContextType.MENTORSHIP_INBOX, archived_at=archived_at),
            _thread(3, ContextType.INQUIRIES_INBOX),
            _thread(4, ContextType.MENTORSHIP_INBOX),
        ]
        self.messages = {
            1: [_in(10, 0, sender="known@ext.com")],
            2: [_in(20, 10, sender="known@ext.com")],
            3: [_in(30, 20)],
            4: [_in(40, 30), _out(41, 40)],
        }
        self.emails = [_email(41, "known@ext.com", True)]
        self.users = [_user(41, "Ann", "Lee")]

        default = await self._list(service=InboxService.MENTORSHIP)
        with_archived = await self._list(service=InboxService.MENTORSHIP, archived=True)
        needs = await self._list(needs_reply=True)

        self.assertEqual(sorted(self._ids(default)), [1, 4])
        self.assertEqual(sorted(self._ids(with_archived)), [1, 2, 4])
        self.assertEqual(
            {r.thread_id: r.archived for r in with_archived.threads},
            {1: False, 2: True, 4: False},
        )
        self.assertEqual(sorted(self._ids(needs)), [1, 3])
        self.assertEqual(default.counts.needs_reply, 1)
        self.assertEqual(with_archived.counts, default.counts)
        self.assertEqual(
            [(s.key, s.needs_reply) for s in default.services],
            [
                (InboxService.MENTORSHIP, 1),
                (InboxService.RECRUITING, 0),
                (InboxService.INQUIRIES, 1),
            ],
        )

    async def test_moved_from_comes_from_the_newest_move_event(self):
        self.threads = [_thread(1, ContextType.INQUIRIES_INBOX)]
        self.messages = {1: [_in(10, 0)]}
        self.moves = {
            1: SimpleNamespace(
                details={"from": "mentorship", "to": "inquiries"}, created_at=_at(5)
            )
        }

        row = (await self._list()).threads[0]
        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertEqual(row.moved_from, InboxService.MENTORSHIP)
        self.assertEqual(detail.moved_at, _at(5))
        self.event_repo.latest_by_subjects.assert_any_await(
            self.session, INBOX_SUBJECT_TYPE, InboxEvent.MOVED, [1]
        )

    async def test_count_needs_reply_covers_every_visible_service(self):
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX),
            _thread(2, ContextType.INQUIRIES_INBOX),
            _thread(3, ContextType.INQUIRIES_INBOX),
        ]
        self.messages = {1: [_in(10, 0)], 2: [_in(20, 0)], 3: [_in(30, 0), _out(31, 1)]}

        self.assertEqual(
            await self.service.count_needs_reply(self.session, _viewer(*_ALL)), 2
        )
        self.assertEqual(
            await self.service.count_needs_reply(
                self.session, _viewer(Permission.INQUIRIES_MANAGE)
            ),
            1,
        )

    async def test_mail_dated_before_the_archive_but_synced_after_it_reopens(self):
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX, archived_at=_at(50)),
            _thread(2, ContextType.MENTORSHIP_INBOX, archived_at=_at(50)),
        ]
        self.messages = {1: [_in(10, 20, stored=60)], 2: [_in(20, 20)]}

        result = await self._list()
        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertEqual(self._ids(result), [1])
        self.assertFalse(result.threads[0].archived)
        self.assertTrue(result.threads[0].needs_reply)
        self.assertEqual(result.counts.needs_reply, 1)
        self.assertTrue(detail.needs_reply)
        self.assertFalse(detail.archived)

    async def test_mail_dated_before_our_reply_but_synced_after_it_needs_reply(self):
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX),
            _thread(2, ContextType.MENTORSHIP_INBOX),
        ]
        self.messages = {
            1: [_out(10, 30), _in(11, 20, stored=40)],
            2: [_out(20, 30), _in(21, 20)],
        }

        result = await self._list(needs_reply=True)

        self.assertEqual(self._ids(result), [1])
        self.assertEqual(
            await self.service.count_needs_reply(self.session, _viewer(*_ALL)), 1
        )


class DetailTest(_Fixture):
    async def test_detail_of_an_inbox_thread(self):
        self.threads = [_thread(1, ContextType.MENTORSHIP_INBOX, subject="Q")]
        self.messages = {
            1: [
                _in(
                    10,
                    0,
                    sender="Asker <asker@ext.com>",
                    attachments=[
                        {"name": "cv.pdf", "size": 1200, "gmailAttachmentId": "g-1"},
                        {"name": "a.png", "size": 30, "gmailAttachmentId": "g-2"},
                    ],
                ),
                _out(11, 5, sent_by=70),
                _in(12, 9, kind="bounce", failed_recipients="asker@ext.com"),
            ]
        }
        self.users = [_user(70, "Mei", "Lin", "May")]

        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertEqual(detail.reply_alias, _MENTORSHIP_ALIAS)
        self.assertEqual(detail.latest_message_id, 12)
        self.assertTrue(detail.can_assign)
        self.assertEqual(detail.open_bounce.bounced_to, "asker@ext.com")
        self.assertEqual(detail.machine_tag, "bounce")
        first, sent, _ = detail.messages
        self.assertEqual(
            [(a.name, a.size, a.attachment_id) for a in first.attachments],
            [("cv.pdf", 1200, 0), ("a.png", 30, 1)],
        )
        self.assertEqual(first.from_, "Asker <asker@ext.com>")
        self.assertEqual(first.inbound_kind, "human")
        self.assertIsNone(first.sent_by_name)
        self.assertEqual(sent.sent_by_name, "May")
        self.assertEqual(sent.at, _at(5))
        dumped = detail.model_dump(by_alias=True)
        self.assertNotIn("gmailAttachmentId", str(dumped))
        self.assertEqual(dumped["messages"][0]["from"], "Asker <asker@ext.com>")
        self.assertEqual(dumped["messages"][0]["attachments"][1]["attachmentId"], 1)
        self.assertIn("openBounce", dumped)
        self.assertIn("replyAlias", dumped)

    async def test_an_unclassified_inbound_with_failed_recipients_is_a_bounce(self):
        self.threads = [_thread(1, ContextType.MENTORSHIP_INBOX)]
        self.messages = {
            1: [
                _out(10, 0, sent_by=70),
                _in(11, 5, kind=None, failed_recipients="asker@ext.com"),
            ]
        }

        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertFalse(detail.needs_reply)
        self.assertEqual(detail.machine_tag, "bounce")
        self.assertEqual(detail.open_bounce.bounced_to, "asker@ext.com")
        self.assertEqual(detail.messages[-1].inbound_kind, "bounce")

    async def test_an_unclassified_inbound_without_failed_recipients_is_human(self):
        self.threads = [_thread(1, ContextType.MENTORSHIP_INBOX)]
        self.messages = {1: [_out(10, 0), _in(11, 5, kind=None)]}

        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertTrue(detail.needs_reply)
        self.assertIsNone(detail.machine_tag)
        self.assertIsNone(detail.open_bounce)
        self.assertEqual(detail.messages[-1].inbound_kind, "human")

    async def test_a_later_outbound_closes_the_bounce(self):
        self.threads = [_thread(1, ContextType.MENTORSHIP_INBOX)]
        self.messages = {
            1: [
                _out(10, 0),
                _in(11, 5, kind="bounce", failed_recipients=""),
                _out(12, 9),
            ]
        }

        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertIsNone(detail.open_bounce)

    async def test_bounce_naming_nobody_on_a_thread_without_contact_is_not_open(self):
        self.threads = [_thread(1, ContextType.MENTORSHIP_INBOX)]
        self.messages = {1: [_in(11, 5, kind="bounce", failed_recipients="")]}

        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertIsNone(detail.open_bounce)
        self.assertEqual(detail.machine_tag, "bounce")

    async def test_bounce_without_named_recipients_points_at_the_contact(self):
        self.threads = [_thread(1, ContextType.MENTORSHIP_INBOX)]
        self.messages = {
            1: [
                _out(10, 0, to="pat@ext.com"),
                _in(11, 5, kind="bounce", failed_recipients=""),
            ]
        }

        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertEqual(detail.open_bounce.bounced_to, "pat@ext.com")

    async def test_recruiting_thread_replies_from_the_recruiting_alias(self):
        self.threads = [_thread(1, ContextType.RECRUITING_INBOX)]
        self.messages = {1: [_in(10, 0)]}

        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertEqual(detail.reply_alias, _RECRUITING_ALIAS)
        self.assertTrue(detail.can_assign)

    async def test_inquiries_without_alias_has_no_reply_alias_and_cannot_assign(self):
        self.threads = [_thread(1, ContextType.INQUIRIES_INBOX)]
        self.messages = {1: [_in(10, 0)]}

        detail = await self.service.get_thread(self.session, _viewer(*_ALL), 1)

        self.assertIsNone(detail.reply_alias)
        self.assertFalse(detail.can_assign)
        self.assertIsNone(detail.moved_from)
        self.assertIsNone(detail.moved_at)


if __name__ == "__main__":
    unittest.main()
