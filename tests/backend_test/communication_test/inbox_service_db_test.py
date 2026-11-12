import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from sqlalchemy import func, select

from backend.common.communication_enums import ContextType, InboxService
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.permissions import Permission
from backend.communication.inbox_aliases import InboxAliases
from backend.communication.inbox_router import InboxRouter
from backend.communication.inbox_service import InboxThreadService
from backend.communication.thread_service import ThreadServiceResolver
from backend.dto.inbox_dto import InboxQueryDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.email_message_entity import EmailMessageEntity
from backend.entity.email_thread_entity import EmailThreadEntity
from backend.entity.event_entity import EventEntity
from backend.entity.notification_entity import NotificationEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.application_repository import ApplicationRepository
from backend.repository.email_message_repository import EmailMessageRepository
from backend.repository.email_thread_repository import EmailThreadRepository
from backend.repository.event_repository import EventRepository
from backend.repository.job_repository import JobRepository
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.repository.user_emails_repository import UserEmailsRepository
from backend.repository.users_repository import UsersRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

_T0 = datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc)
_VIEWER = UserContextDto(
    sub="v",
    primary_email="viewer@circlecat.org",
    user_id=None,
    permissions=frozenset({
        Permission.MENTORSHIP_ADMIN_WRITE,
        Permission.RECRUITING_APPLICATION_ADVANCE,
        Permission.INQUIRIES_MANAGE,
    }),
)


def _at(minutes):
    return _T0 + timedelta(minutes=minutes)


class InboxListOnARealSessionTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.service = InboxThreadService(
            thread_repository=EmailThreadRepository(),
            message_repository=EmailMessageRepository(),
            user_emails_repository=UserEmailsRepository(),
            users_repository=UsersRepository(),
            application_repository=ApplicationRepository(),
            round_repository=MentorshipRoundRepository(),
            event_repository=EventRepository(),
            thread_service_resolver=ThreadServiceResolver(
                job_repository=JobRepository()
            ),
            aliases=InboxAliases(mentorship="mentorship-db@example.com"),
            person_email_service=Mock(),
            round_participants_repository=MentorshipRoundParticipantsRepository(),
            rounds_service=Mock(),
            gmail_client=Mock(),
            logger=Mock(),
        )
        self.baseline = await self._list()

    async def _list(self, **query):
        return await self.service.list_threads(
            self.session, _VIEWER, InboxQueryDto(**query)
        )

    async def _thread(self, key, context_type, archived_at=None, context_id=None):
        thread = EmailThreadEntity(
            gmail_thread_id=f"g-inbox-list-db-{key}",
            subject=f"Question {key}",
            context_type=context_type,
            context_id=context_id,
            archived_at=archived_at,
        )
        await self.insert_entities([thread])
        return thread

    async def _message(self, thread, key, direction, minutes, sender=None, kind=None):
        await self.insert_entities([
            EmailMessageEntity(
                thread_id=thread.thread_id,
                gmail_message_id=f"g-inbox-list-db-{key}",
                direction=direction,
                from_address=sender,
                to_addresses="mentorship-db@example.com",
                snippet=f"snippet {key}",
                gmail_internal_date=_at(minutes),
                created_at=_at(minutes),
                inbound_kind=kind,
            )
        ])

    async def _moved(self, thread, from_service, minutes):
        await self.insert_entities([
            EventEntity(
                subject_type=INBOX_SUBJECT_TYPE,
                subject_id=thread.thread_id,
                event_type=InboxEvent.MOVED,
                details={"from": from_service, "to": "inquiries"},
                created_at=_at(minutes),
            )
        ])

    async def test_order_counts_and_matching_match_the_prototype(self):
        user = UsersEntity(
            first_name="Xiao",
            last_name="Wang",
            preferred_name="Sofia",
            timezone="UTC",
            timezone_updated_at=_T0,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
        )
        await self.insert_entities([user])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=user.user_id,
                email="w.xiao.inbox-db@example.com",
                is_primary=False,
            )
        ])
        asked = await self._thread("asked", ContextType.MENTORSHIP_INBOX)
        await self._message(
            asked,
            "asked-1",
            "inbound",
            10,
            '"Wang" <W.Xiao.Inbox-DB@Example.com>',
            "human",
        )
        moved = await self._thread("moved", ContextType.INQUIRIES_INBOX)
        await self._message(
            moved, "moved-1", "inbound", 30, "stranger@ext.com", "human"
        )
        await self._moved(moved, "recruiting", 31)
        await self._moved(moved, "mentorship", 32)
        answered = await self._thread("answered", ContextType.MENTORSHIP_INBOX)
        await self._message(answered, "answered-1", "inbound", 5, "a@ext.com", "human")
        await self._message(
            answered, "answered-2", "outbound", 60, "mentorship-db@example.com"
        )
        archived = await self._thread(
            "archived", ContextType.MENTORSHIP_INBOX, archived_at=_at(25)
        )
        await self._message(archived, "archived-1", "inbound", 20, "b@ext.com", "human")
        assigned = await self._thread("assigned", ContextType.ACTIVITY, context_id=8)
        await self._message(assigned, "assigned-1", "inbound", 40, "c@ext.com", "human")
        started = await self._thread("started", ContextType.APPLICATION, context_id=57)
        await self._message(started, "started-1", "outbound", 0, "careers@example.com")
        await self._message(started, "started-2", "inbound", 45, "d@ext.com", "human")
        mine = {
            asked.thread_id,
            moved.thread_id,
            answered.thread_id,
            archived.thread_id,
            assigned.thread_id,
            started.thread_id,
        }

        result = await self._list()
        with_archived = await self._list(archived=True)

        self.assertEqual(
            [r.thread_id for r in result.threads if r.thread_id in mine],
            [moved.thread_id, asked.thread_id, answered.thread_id],
        )
        self.assertEqual(
            [r.thread_id for r in with_archived.threads if r.thread_id in mine],
            [moved.thread_id, asked.thread_id, answered.thread_id, archived.thread_id],
        )
        self.assertEqual(
            result.counts.needs_reply, self.baseline.counts.needs_reply + 2
        )
        before = {s.key: s.needs_reply for s in self.baseline.services}
        after = {s.key: s.needs_reply for s in result.services}
        self.assertEqual(
            after[InboxService.MENTORSHIP], before[InboxService.MENTORSHIP] + 1
        )
        self.assertEqual(
            after[InboxService.INQUIRIES], before[InboxService.INQUIRIES] + 1
        )

        rows = {r.thread_id: r for r in result.threads}
        self.assertEqual(rows[asked.thread_id].sender, "w.xiao.inbox-db@example.com")
        self.assertEqual(rows[asked.thread_id].person.name, "Sofia")
        self.assertEqual(rows[asked.thread_id].matched_by, "alternative")
        self.assertTrue(rows[moved.thread_id].no_matching_user)
        self.assertEqual(rows[moved.thread_id].moved_from, InboxService.MENTORSHIP)

        detail = await self.service.get_thread(self.session, _VIEWER, moved.thread_id)
        self.assertEqual(detail.moved_at, _at(32))
        self.assertIsNone(detail.reply_alias)
        self.assertEqual(
            await self.service.count_needs_reply(self.session, _VIEWER),
            await self._baseline_needs_reply() + 2,
        )

    async def _baseline_needs_reply(self):
        return sum(s.needs_reply for s in self.baseline.services)


_OPS = UserContextDto(
    sub="ops",
    primary_email="ops@circlecat.org",
    user_id=None,
    permissions=frozenset({Permission.OPS_MAINTAIN}),
)
_MAILBOX = "purrf-delete-db@example.com"


class InboxDeleteOnARealSessionTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.threads = EmailThreadRepository()
        self.service = InboxThreadService(
            thread_repository=self.threads,
            message_repository=EmailMessageRepository(),
            user_emails_repository=UserEmailsRepository(),
            users_repository=UsersRepository(),
            application_repository=ApplicationRepository(),
            round_repository=MentorshipRoundRepository(),
            event_repository=EventRepository(),
            thread_service_resolver=ThreadServiceResolver(
                job_repository=JobRepository()
            ),
            aliases=InboxAliases(inquiries="inquiries-db@example.com"),
            person_email_service=Mock(),
            round_participants_repository=MentorshipRoundParticipantsRepository(),
            rounds_service=Mock(),
            gmail_client=Mock(),
            logger=Mock(),
        )
        self.user = UsersEntity(
            first_name="Ops",
            last_name="Person",
            timezone="UTC",
            timezone_updated_at=_T0,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
        )
        await self.insert_entities([self.user])

    async def _thread(self, key, context_type=ContextType.UNSORTED_INBOX):
        thread = EmailThreadEntity(
            gmail_thread_id=f"g-inbox-delete-db-{key}",
            subject=f"Mail {key}",
            context_type=context_type,
        )
        await self.insert_entities([thread])
        message = EmailMessageEntity(
            thread_id=thread.thread_id,
            gmail_message_id=f"g-inbox-delete-db-{key}-1",
            direction="inbound",
            from_address="sender@ext.com",
            to_addresses=_MAILBOX,
            gmail_internal_date=_at(0),
            attachments=[{"name": "a.pdf", "size": 3, "gmailAttachmentId": "x"}],
        )
        event = EventEntity(
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=thread.thread_id,
            event_type=InboxEvent.NEEDS_REPLY,
            details={"service": "unsorted"},
        )
        await self.insert_entities([message, event])
        await self.insert_entities([
            NotificationEntity(user_id=self.user.user_id, event_id=event.event_id)
        ])
        return thread

    async def _count(self, entity, column, ids):
        result = await self.session.execute(
            select(func.count()).select_from(entity).where(column.in_(ids))
        )
        return result.scalar_one()

    async def _left(self, thread_ids):
        events = select(EventEntity.event_id).where(
            EventEntity.subject_type == INBOX_SUBJECT_TYPE,
            EventEntity.subject_id.in_(thread_ids),
        )
        notifications = await self.session.execute(
            select(func.count())
            .select_from(NotificationEntity)
            .where(NotificationEntity.event_id.in_(events))
        )
        return {
            "threads": await self._count(
                EmailThreadEntity, EmailThreadEntity.thread_id, thread_ids
            ),
            "messages": await self._count(
                EmailMessageEntity, EmailMessageEntity.thread_id, thread_ids
            ),
            "events": await self._count(EventEntity, EventEntity.event_id, events),
            "notifications": notifications.scalar_one(),
        }

    async def test_delete_removes_threads_with_their_messages_events_and_notifications(
        self,
    ):
        first = await self._thread("first")
        second = await self._thread("second")
        kept = await self._thread("kept")
        ids = [first.thread_id, second.thread_id]

        deleted = await self.service.delete(self.session, _OPS, ids + [ids[0]])

        self.assertEqual(deleted, 2)
        self.assertEqual(
            await self._left(ids),
            {"threads": 0, "messages": 0, "events": 0, "notifications": 0},
        )
        self.assertEqual(
            await self._left([kept.thread_id]),
            {"threads": 1, "messages": 1, "events": 1, "notifications": 1},
        )

    async def test_a_thread_of_another_service_rejects_the_whole_request(self):
        unsorted = await self._thread("mixed-unsorted")
        inquiry = await self._thread("mixed-inquiry", ContextType.INQUIRIES_INBOX)
        viewer = UserContextDto(
            sub="both",
            primary_email="both@circlecat.org",
            user_id=None,
            permissions=frozenset({
                Permission.OPS_MAINTAIN,
                Permission.INQUIRIES_MANAGE,
            }),
        )
        ids = [unsorted.thread_id, inquiry.thread_id]

        with self.assertRaisesRegex(ValueError, "not in the Unsorted inbox"):
            await self.service.delete(self.session, viewer, ids)

        self.assertEqual(
            await self._left(ids),
            {"threads": 2, "messages": 2, "events": 2, "notifications": 2},
        )

    async def test_an_unknown_id_rejects_the_whole_request(self):
        unsorted = await self._thread("unknown-unsorted")
        missing = unsorted.thread_id + 10_000

        with self.assertRaisesRegex(ValueError, f"thread {missing} not found"):
            await self.service.delete(self.session, _OPS, [unsorted.thread_id, missing])

        self.assertEqual((await self._left([unsorted.thread_id]))["threads"], 1)

    async def test_new_mail_in_a_deleted_thread_routes_it_into_unsorted_again(self):
        gmail = Mock()
        gmail.owns_address.return_value = False
        gmail.list_thread_message_ids.return_value = ["m1"]
        gmail.get_messages.return_value = [
            {
                "gmail_message_id": "m1",
                "from_address": "sender@ext.com",
                "recipients": [_MAILBOX],
                "subject": "Straight to the mailbox",
                "gmail_internal_date": "1000",
            }
        ]
        gmail.list_send_as_addresses.return_value = {_MAILBOX}
        router = InboxRouter(
            gmail_client=gmail,
            thread_repository=self.threads,
            aliases=InboxAliases(
                inquiries="inquiries-db@example.com", unsorted_enabled=True
            ),
            logger=Mock(),
        )
        gid = "g-inbox-delete-db-reroute"

        first = (await router.route(self.session, gid, _MAILBOX)).thread
        self.assertEqual(first.context_type, ContextType.UNSORTED_INBOX)
        first_id = first.thread_id
        await self.service.delete(self.session, _OPS, [first_id])
        self.assertIsNone(await self.threads.get_by_gmail_thread_id(self.session, gid))

        again = (await router.route(self.session, gid, _MAILBOX)).thread

        self.assertEqual(again.context_type, ContextType.UNSORTED_INBOX)
        self.assertNotEqual(again.thread_id, first_id)
        self.assertEqual(
            (await self.threads.get_by_gmail_thread_id(self.session, gid)).thread_id,
            again.thread_id,
        )


if __name__ == "__main__":
    unittest.main()
