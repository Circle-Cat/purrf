"""Turns newly synced mail on an Inbox thread into notification events.

Application threads are skipped: PUR-717's ``email_received`` and
``email_bounced`` already tell that thread's senders.
"""

from backend.common.communication_enums import ContextType
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.communication.thread_alerts import alerts_after_sync
from backend.notification_management.event_recorder import record_event


class InboxNotifier:
    def __init__(self, message_repository, thread_service_resolver):
        """
        Args:
            message_repository (EmailMessageRepository): Reads the whole thread.
            thread_service_resolver (ThreadServiceResolver): Names the thread's service.
        """
        self._messages = message_repository
        self._services = thread_service_resolver

    async def after_sync(self, session, thread, new_messages):
        """Record the events these newly synced messages call for. Does not commit.

        NEEDS_REPLY is recorded once, when the new messages tip the thread
        from not needing a reply into needing one. BOUNCED is recorded per
        new bounce, for whoever sent our newest message before it; a bounce
        whose sender is unknown records nothing.

        Args:
            session (AsyncSession): The active DB session.
            thread (EmailThreadEntity): The synced thread.
            new_messages (list[EmailMessageEntity]): Messages this sync stored.

        Returns:
            bool: True when NEEDS_REPLY was recorded.
        """
        if thread.context_type == ContextType.APPLICATION or not new_messages:
            return False
        messages = await self._messages.list_by_thread(session, thread.thread_id)
        alerts = alerts_after_sync(thread, messages, new_messages)

        for bounce in alerts.bounces:
            if bounce.sender_user_id is None:
                continue
            await record_event(
                session,
                subject_type=INBOX_SUBJECT_TYPE,
                subject_id=thread.thread_id,
                actor_id=None,
                event_type=InboxEvent.BOUNCED,
                details={
                    "bouncedTo": bounce.bounced_to,
                    "subject": bounce.subject,
                    "senderUserId": bounce.sender_user_id,
                },
            )

        if alerts.needs_reply_from is None:
            return False
        service = await self._services.service_of(session, thread)
        await record_event(
            session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=thread.thread_id,
            actor_id=None,
            event_type=InboxEvent.NEEDS_REPLY,
            details={
                "service": service,
                "subject": thread.subject,
                "from": alerts.needs_reply_from,
            },
        )
        return True
