"""Turns newly synced mail on an Inbox thread into notification events.

Application threads are skipped: PUR-717's ``email_received`` and
``email_bounced`` already tell that thread's senders.
"""

from email.utils import getaddresses

from backend.common.communication_enums import ContextType, EmailDirection
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.communication.inbox_state import (
    is_bounce,
    is_human_inbound,
    message_time,
    needs_reply,
)
from backend.notification_management.event_recorder import record_event


def _bounced_to(bounce, original):
    named = [a for _, a in getaddresses([bounce.failed_recipients or ""]) if a]
    if named:
        return ", ".join(named)
    return original.to_addresses or ""


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
        new_ids = {m.message_id for m in new_messages}
        before = [m for m in messages if m.message_id not in new_ids]

        for bounce in (m for m in new_messages if is_bounce(m)):
            await self._record_bounce(session, thread, messages, bounce)

        if needs_reply(before, thread.archived_at) or not needs_reply(
            messages, thread.archived_at
        ):
            return False
        newest = max((m for m in new_messages if is_human_inbound(m)), key=message_time)
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
                "from": newest.from_address,
            },
        )
        return True

    async def _record_bounce(self, session, thread, messages, bounce):
        bounced_at = message_time(bounce)
        earlier = [
            m
            for m in messages
            if m.direction == EmailDirection.OUTBOUND and message_time(m) <= bounced_at
        ]
        if not earlier:
            return
        original = max(earlier, key=message_time)
        if original.sent_by_user_id is None:
            return
        await record_event(
            session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=thread.thread_id,
            actor_id=None,
            event_type=InboxEvent.BOUNCED,
            details={
                "bouncedTo": _bounced_to(bounce, original),
                "subject": original.subject or thread.subject,
                "senderUserId": original.sent_by_user_id,
            },
        )
