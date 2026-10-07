import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from backend.common.communication_enums import ContextType, InboxService
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.permissions import Permission
from backend.communication.inbox_aliases import InboxAliases
from backend.communication.inbox_service import InboxThreadService
from backend.communication.thread_service import ThreadServiceResolver
from backend.dto.inbox_dto import InboxQueryDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.email_message_entity import EmailMessageEntity
from backend.entity.email_thread_entity import EmailThreadEntity
from backend.entity.event_entity import EventEntity
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
    permissions=frozenset(
        {
            Permission.MENTORSHIP_ADMIN_WRITE,
            Permission.RECRUITING_APPLICATION_ADVANCE,
            Permission.INQUIRIES_MANAGE,
        }
    ),
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
            job_repository=JobRepository(),
            application_repository=ApplicationRepository(),
            round_repository=MentorshipRoundRepository(),
            event_repository=EventRepository(),
            thread_service_resolver=ThreadServiceResolver(job_repository=JobRepository()),
            conversation_service=SimpleNamespace(sender_address="careers@example.com"),
            aliases=InboxAliases(mentorship="mentorship-db@example.com"),
            gmail_client=Mock(),
            round_participants_repository=MentorshipRoundParticipantsRepository(),
            rounds_service=Mock(),
        )
        self.baseline = await self._list()

    async def _list(self, **query):
        return await self.service.list_threads(
            self.session, _VIEWER, InboxQueryDto(**query)
        )

    async def _thread(self, key, context_type, archived_at=None):
        thread = EmailThreadEntity(
            gmail_thread_id=f"g-inbox-list-db-{key}",
            subject=f"Question {key}",
            context_type=context_type,
            archived_at=archived_at,
        )
        await self.insert_entities([thread])
        return thread

    async def _message(self, thread, key, direction, minutes, sender=None, kind=None):
        await self.insert_entities(
            [
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
            ]
        )

    async def _moved(self, thread, from_service, minutes):
        await self.insert_entities(
            [
                EventEntity(
                    subject_type=INBOX_SUBJECT_TYPE,
                    subject_id=thread.thread_id,
                    event_type=InboxEvent.MOVED,
                    details={"from": from_service, "to": "inquiries"},
                    created_at=_at(minutes),
                )
            ]
        )

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
        await self.insert_entities(
            [
                UserEmailsEntity(
                    user_id=user.user_id,
                    email="w.xiao.inbox-db@example.com",
                    is_primary=False,
                )
            ]
        )
        asked = await self._thread("asked", ContextType.MENTORSHIP_INBOX)
        await self._message(
            asked, "asked-1", "inbound", 10, '"Wang" <W.Xiao.Inbox-DB@Example.com>', "human"
        )
        moved = await self._thread("moved", ContextType.INQUIRIES_INBOX)
        await self._message(moved, "moved-1", "inbound", 30, "stranger@ext.com", "human")
        await self._moved(moved, "recruiting", 31)
        await self._moved(moved, "mentorship", 32)
        answered = await self._thread("answered", ContextType.MENTORSHIP_INBOX)
        await self._message(answered, "answered-1", "inbound", 5, "a@ext.com", "human")
        await self._message(answered, "answered-2", "outbound", 60, "mentorship-db@example.com")
        archived = await self._thread(
            "archived", ContextType.MENTORSHIP_INBOX, archived_at=_at(25)
        )
        await self._message(archived, "archived-1", "inbound", 20, "b@ext.com", "human")
        mine = {asked.thread_id, moved.thread_id, answered.thread_id, archived.thread_id}

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
        self.assertEqual(
            result.counts.unassigned, self.baseline.counts.unassigned + 1
        )
        before = {s.key: s.needs_reply for s in self.baseline.services}
        after = {s.key: s.needs_reply for s in result.services}
        self.assertEqual(after[InboxService.MENTORSHIP], before[InboxService.MENTORSHIP] + 1)
        self.assertEqual(after[InboxService.INQUIRIES], before[InboxService.INQUIRIES] + 1)

        rows = {r.thread_id: r for r in result.threads}
        self.assertEqual(rows[asked.thread_id].sender, "w.xiao.inbox-db@example.com")
        self.assertEqual(rows[asked.thread_id].person.name, "Sofia")
        self.assertEqual(rows[asked.thread_id].matched_by, "alternative")
        self.assertTrue(rows[asked.thread_id].unassigned)
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


if __name__ == "__main__":
    unittest.main()
