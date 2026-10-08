"""Inbox thread actions: reply, archive, assign and move.

Every public method is an entry point: it checks, writes, records an event,
then commits, and answers with the thread as the viewer now sees it (None
once it has left the Inbox or the viewer's services). A rejected action raises
before anything is written.
"""

from datetime import datetime, timezone

from backend.common.communication_enums import INBOX_CONTEXT, ContextType, InboxService
from backend.common.exceptions import ConflictError
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.common.recruiting_enums import JobKind
from backend.communication.inbox_access import visible_services
from backend.communication.inbox_rows import can_assign, facts_of, reply_contact
from backend.notification_management.event_recorder import record_event


def reply_subject(subject: str | None) -> str:
    """``Re: <subject>``, unless the subject already says so."""
    subject = (subject or "").strip()
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}".strip()


class InboxThreadWrites:
    """The write half of ``InboxThreadService``; relies on its repositories."""

    async def reply(self, session, user, thread_id, body, last_seen_message_id):
        """Send a reply from the thread's service alias. Commits.

        Args:
            session (AsyncSession): The active DB session.
            user (UserContextDto): The sender.
            thread_id (int): The thread.
            body (str): HTML body.
            last_seen_message_id (int | None): The newest message the sender saw.

        Returns:
            InboxThreadDetailDto: The thread with the reply in it.

        Raises:
            ValueError: Thread not found or not visible; no alias in this
                environment; nobody to reply to.
            ConflictError: ``THREAD_CHANGED`` when a newer message arrived.
        """
        thread, service = await self._load_visible(session, user, thread_id)
        messages = await self._messages.list_by_thread(session, thread_id)
        if messages and messages[-1].message_id != last_seen_message_id:
            raise ConflictError(
                "This thread has new messages. Read them before sending.",
                code="THREAD_CHANGED",
            )
        alias = self._aliases.alias_of(service)
        if alias is None:
            raise ValueError("This environment has no alias for this inbox")
        contact = reply_contact(messages)
        if contact is None:
            raise ValueError("This thread has nobody to reply to")
        subject = reply_subject(thread.subject)

        await self._conversation.send(
            session,
            user_id=thread.user_id,
            context_type=thread.context_type,
            context_id=thread.context_id,
            to=[contact],
            subject=subject,
            body=body,
            sender_user_id=user.user_id,
            thread_id=thread_id,
            sender_address=alias,
        )
        await session.commit()
        return await self.get_thread(session, user, thread_id)

    async def archive(self, session, user, thread_id):
        """Archive a thread until a person writes in again. Commits.

        Raises:
            ValueError: Thread not found or not visible, or already archived.
        """
        thread, _, facts = await self._load_for_write(session, user, thread_id)
        if facts.archived:
            raise ValueError("This thread is already archived")
        thread.archived_at = datetime.now(timezone.utc)
        thread.archived_by_user_id = user.user_id
        return await self._finish(session, user, thread, InboxEvent.ARCHIVED)

    async def unarchive(self, session, user, thread_id):
        """Bring an archived thread back. Commits.

        Raises:
            ValueError: Thread not found or not visible, or not archived.
        """
        thread, _, facts = await self._load_for_write(session, user, thread_id)
        if not facts.archived:
            raise ValueError("This thread is not archived")
        thread.archived_at = None
        thread.archived_by_user_id = None
        return await self._finish(session, user, thread, InboxEvent.UNARCHIVED)

    async def assign(
        self, session, user, thread_id, person_id, round_id=None, application_id=None
    ):
        """Attach a thread to a person and a round or an application. Commits.

        A Mentorship thread takes ``round_id`` (any existing round, registered
        or not). A Recruiting thread takes ``application_id`` of one of the
        person's applications to an EMPLOYMENT job, rejected ones included.
        The thread then leaves the Inbox and is read where it was attached.

        Args:
            session (AsyncSession): The active DB session.
            user (UserContextDto): The viewer.
            thread_id (int): The thread.
            person_id (int): Who the thread is with.
            round_id (int | None): The round, for Mentorship.
            application_id (int | None): The application, for Recruiting.

        Returns:
            None: The thread is no longer in the Inbox.

        Raises:
            ValueError: Thread not found or not visible; the thread cannot be
                assigned; the wrong kind of target; the round, person or
                application does not exist; the application is someone
                else's or not to an EMPLOYMENT job.
        """
        thread, service, facts = await self._load_for_write(session, user, thread_id)
        if not can_assign(service, facts):
            raise ValueError("This thread cannot be assigned")
        if service == InboxService.MENTORSHIP:
            if round_id is None or application_id is not None:
                raise ValueError("A Mentorship thread is assigned to a round")
            context_type, context_id = ContextType.ACTIVITY, round_id
            details = {"userId": person_id, "roundId": round_id}
            if await self._rounds.get_by_round_id(session, round_id) is None:
                raise ValueError(f"round {round_id} not found")
            if not await self._users.get_all_by_ids(session, [person_id]):
                raise ValueError(f"user {person_id} not found")
        else:
            if application_id is None or round_id is not None:
                raise ValueError("A Recruiting thread is assigned to an application")
            await self._check_application(session, person_id, application_id)
            context_type, context_id = ContextType.APPLICATION, application_id
            details = {"userId": person_id, "applicationId": application_id}

        thread.user_id = person_id
        thread.context_type = context_type
        thread.context_id = context_id
        await self._record(session, user, thread, InboxEvent.ASSIGNED, details)
        return None

    async def move(self, session, user, thread_id, target: InboxService):
        """Move a thread to another service's inbox, unassigned and unarchived. Commits.

        Args:
            session (AsyncSession): The active DB session.
            user (UserContextDto): The viewer.
            thread_id (int): The thread.
            target (InboxService): Where it goes.

        Returns:
            InboxThreadDetailDto | None: The moved thread, or None when the
                viewer cannot see the target service.

        Raises:
            ValueError: Thread not found or not visible, tracked, or already
                in ``target``.
        """
        thread, service, facts = await self._load_for_write(session, user, thread_id)
        if facts.tracked:
            raise ValueError("A thread we started cannot be moved")
        if target == service:
            raise ValueError(f"This thread is already in {target}")
        thread.context_type = INBOX_CONTEXT[target]
        thread.context_id = None
        thread.user_id = None
        thread.archived_at = None
        thread.archived_by_user_id = None
        await record_event(
            session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=thread.thread_id,
            actor_id=user.user_id,
            event_type=InboxEvent.MOVED,
            details={"from": str(service), "to": str(target)},
        )
        await session.commit()
        if target not in visible_services(user):
            return None
        return await self.get_thread(session, user, thread.thread_id)

    async def _load_for_write(self, session, user, thread_id):
        thread, service = await self._load_visible(session, user, thread_id)
        messages = await self._messages.list_by_thread(session, thread_id)
        return thread, service, facts_of(thread, messages)

    async def _check_application(self, session, person_id, application_id):
        pair = await self._applications.get_with_job(session, application_id)
        if pair is None:
            raise ValueError(f"application {application_id} not found")
        application, job = pair
        if application.user_id != person_id:
            raise ValueError(
                f"application {application_id} does not belong to user {person_id}"
            )
        if job.kind != JobKind.EMPLOYMENT:
            raise ValueError("Only an employment job can be assigned from the Inbox")

    async def _finish(self, session, user, thread, event_type, details=None):
        await self._record(session, user, thread, event_type, details)
        return await self.get_thread(session, user, thread.thread_id)

    @staticmethod
    async def _record(session, user, thread, event_type, details=None):
        await record_event(
            session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=thread.thread_id,
            actor_id=user.user_id,
            event_type=event_type,
            details=details,
        )
        await session.commit()
