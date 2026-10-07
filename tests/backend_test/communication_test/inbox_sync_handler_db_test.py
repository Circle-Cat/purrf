import unittest
from unittest.mock import Mock

from sqlalchemy import select

from backend.common.communication_enums import ContextType, EmailDirection
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.communication import recipient_resolvers  # noqa: F401 (registers)
from backend.communication.email_context_registry import EmailContextRegistry
from backend.communication.email_conversation_service import EmailConversationService
from backend.communication.gmail_sync_service import GmailSyncService, PushOutcome
from backend.communication.inbox_aliases import InboxAliases
from backend.communication.inbox_notifier import InboxNotifier
from backend.communication.inbox_router import InboxRouter
from backend.communication.inbox_sync_handler import InboxSyncHandler
from backend.communication.thread_service import ThreadServiceResolver
from backend.entity.email_message_entity import EmailMessageEntity
from backend.entity.email_thread_entity import EmailThreadEntity
from backend.entity.event_entity import EventEntity
from backend.ops.ops_alert_service import OpsAlertService
from backend.repository.email_message_repository import EmailMessageRepository
from backend.repository.email_thread_repository import EmailThreadRepository
from backend.repository.gmail_sync_state_repository import GmailSyncStateRepository
from backend.repository.job_repository import JobRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

_MAILBOX = "purrf-inbox-db-test@example.com"
_ALIAS = "mentorship-inbox-db-test@example.com"
_GMAIL_THREAD = "g-inbox-handler-db-test"


def _message(gmail_id, internal_date):
    return {
        "gmail_message_id": gmail_id,
        "from_address": "Asker <asker@ext.com>",
        "to_addresses": _ALIAS,
        "recipients": [_ALIAS, _MAILBOX],
        "subject": "A question",
        "html": "<p>Hi</p>",
        "plain": "Hi",
        "snippet": "Hi",
        "rfc822_message_id": f"<{gmail_id}@ext.com>",
        "gmail_internal_date": internal_date,
    }


class TestInboxSyncOnARealSession(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mail = {
            "m1": _message("m1", "1700000000000"),
            "m2": _message("m2", "1700000060000"),
        }
        self.listed = ["m1"]
        self.gmail = Mock()
        self.gmail.get_profile.return_value = {
            "email_address": _MAILBOX,
            "history_id": 500,
        }
        self.gmail.owns_address.side_effect = lambda a: a in (_ALIAS, _MAILBOX)
        self.gmail.list_thread_message_ids.side_effect = lambda gid: list(self.listed)
        self.gmail.get_messages.side_effect = lambda ids: [self.mail[i] for i in ids]
        self.gmail.list_send_as_addresses.return_value = {_MAILBOX, _ALIAS}

        self.threads = EmailThreadRepository()
        messages = EmailMessageRepository()
        handler = InboxSyncHandler(
            conversation_service=EmailConversationService(
                gmail_client=self.gmail,
                thread_repository=self.threads,
                message_repository=messages,
                sender_address=_ALIAS,
            ),
            thread_repository=self.threads,
            notifier=InboxNotifier(
                message_repository=messages,
                thread_service_resolver=ThreadServiceResolver(
                    job_repository=JobRepository()
                ),
            ),
            logger=Mock(),
        )
        registry = EmailContextRegistry()
        registry.register(ContextType.MENTORSHIP_INBOX, handler)
        self.service = GmailSyncService(
            gmail_client=self.gmail,
            state_repository=GmailSyncStateRepository(),
            thread_repository=self.threads,
            context_registry=registry,
            ops_alerts=OpsAlertService(logger=Mock()),
            watch_topic="projects/p/topics/gmail",
            database=Mock(),
            logger=Mock(),
            inbox_router=InboxRouter(
                gmail_client=self.gmail,
                thread_repository=self.threads,
                aliases=InboxAliases(mentorship=_ALIAS),
                logger=Mock(),
            ),
        )
        self.handler = handler
        await GmailSyncStateRepository().create(self.session, _MAILBOX, 100)
        await self.session.commit()

    async def _push(self, push_id, history_id):
        self.gmail.list_history.return_value = {
            "history_id": history_id,
            "thread_ids": {_GMAIL_THREAD},
        }
        return await self.service.handle_push(self.session, _MAILBOX, push_id)

    async def _thread(self):
        return await self.threads.get_by_gmail_thread_id(self.session, _GMAIL_THREAD)

    async def _needs_reply_events(self, thread_id):
        result = await self.session.execute(
            select(EventEntity).where(
                EventEntity.subject_type == INBOX_SUBJECT_TYPE,
                EventEntity.subject_id == thread_id,
                EventEntity.event_type == InboxEvent.NEEDS_REPLY,
            )
        )
        return result.scalars().all()

    async def test_a_routed_thread_stores_its_mail_and_needs_a_reply_once(self):
        self.assertEqual(await self._push(120, 150), PushOutcome.ACK)
        self.listed = ["m1", "m2"]
        self.assertEqual(await self._push(200, 250), PushOutcome.ACK)

        thread = await self._thread()
        self.assertEqual(thread.context_type, ContextType.MENTORSHIP_INBOX)
        stored = await self.session.execute(
            select(EmailMessageEntity).where(
                EmailMessageEntity.thread_id == thread.thread_id
            )
        )
        stored = stored.scalars().all()
        self.assertEqual(sorted(m.gmail_message_id for m in stored), ["m1", "m2"])
        self.assertTrue(all(m.direction == EmailDirection.INBOUND for m in stored))
        (event,) = await self._needs_reply_events(thread.thread_id)
        self.assertEqual(
            event.details,
            {
                "service": "mentorship",
                "subject": "A question",
                "from": "Asker <asker@ext.com>",
            },
        )

    async def test_resync_sweeps_inbox_threads_and_skips_application_ones(self):
        inbox = await self.threads.create(
            self.session,
            user_id=None,
            gmail_thread_id=_GMAIL_THREAD,
            subject="A question",
            context_type=ContextType.MENTORSHIP_INBOX,
            context_id=None,
        )
        await self.threads.create(
            self.session,
            user_id=None,
            gmail_thread_id="g-application-db-test",
            subject="Your application",
            context_type=ContextType.APPLICATION,
            context_id=None,
        )
        await self.session.commit()

        listed = await self.threads.list_by_context_types(
            self.session, [ContextType.MENTORSHIP_INBOX, ContextType.ACTIVITY]
        )
        result = await self.handler.resync_all(self.session)

        self.assertIn(inbox.thread_id, [t.thread_id for t in listed])
        self.assertNotIn("g-application-db-test", [t.gmail_thread_id for t in listed])
        self.assertEqual(result["failed"], 0)
        self.gmail.list_thread_message_ids.assert_any_call(_GMAIL_THREAD)
        self.assertNotIn(
            "g-application-db-test",
            [c.args[0] for c in self.gmail.list_thread_message_ids.call_args_list],
        )
        self.assertEqual(len(await self._needs_reply_events(inbox.thread_id)), 1)
        synced_at = await self.session.scalar(
            select(EmailThreadEntity.synced_at).where(
                EmailThreadEntity.thread_id == inbox.thread_id
            )
        )
        self.assertIsNotNone(synced_at)


if __name__ == "__main__":
    unittest.main()
