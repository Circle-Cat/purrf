"""Turns new mail on a person's round thread (ACTIVITY) into mentorship events."""

from backend.common.communication_enums import ContextType
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE
from backend.common.mentorship_enums import MentorshipEvent
from backend.common.name_utils import display_name_of
from backend.communication.thread_alerts import alerts_after_sync
from backend.notification_management.event_recorder import record_event


class ParticipantEmailNotifier:
    def __init__(self, message_repository, users_repository):
        """
        Args:
            message_repository (EmailMessageRepository): Reads the whole thread.
            users_repository (UsersRepository): Names the person.
        """
        self._messages = message_repository
        self._users = users_repository

    async def after_sync(self, session, thread, new_messages):
        """Record what new mail on a round thread calls for. Does not commit.

        EMAIL_RECEIVED once, when the new messages tip the thread into needing
        a reply; EMAIL_BOUNCED per new bounce that answers one of our sends.

        Args:
            session (AsyncSession): The active DB session.
            thread (EmailThreadEntity): An ACTIVITY thread; ``context_id`` is the round.
                Threads of another context, or without a person or round, are ignored.
            new_messages (list[EmailMessageEntity]): Messages this sync stored.

        Returns:
            bool: True when EMAIL_RECEIVED was recorded.
        """
        if (
            not new_messages
            or thread.context_type != ContextType.ACTIVITY
            or thread.user_id is None
            or thread.context_id is None
        ):
            return False
        messages = await self._messages.list_by_thread(session, thread.thread_id)
        alerts = alerts_after_sync(thread, messages, new_messages)
        if not alerts.bounces and alerts.needs_reply_from is None:
            return False
        person = await self._users.get_user_by_user_id(session, thread.user_id)
        about = {
            "roundId": thread.context_id,
            "userId": thread.user_id,
            "personName": display_name_of(person),
            "threadId": thread.thread_id,
        }
        for bounce in alerts.bounces:
            await self._record(
                session,
                thread,
                MentorshipEvent.EMAIL_BOUNCED,
                {**about, "subject": bounce.subject, "bouncedTo": bounce.bounced_to},
            )
        if alerts.needs_reply_from is None:
            return False
        await self._record(
            session,
            thread,
            MentorshipEvent.EMAIL_RECEIVED,
            {**about, "subject": thread.subject, "from": alerts.needs_reply_from},
        )
        return True

    @staticmethod
    async def _record(session, thread, event_type, details):
        await record_event(
            session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=thread.thread_id,
            actor_id=None,
            event_type=event_type,
            details=details,
        )
