"""Inbox thread actions: reply, archive, assign and move.

Every public method is an entry point: it checks, writes, records an event,
then commits, and answers with the thread as the viewer now sees it. A
rejected action raises before anything is written.
"""

from datetime import datetime, timezone

from backend.common.communication_enums import INBOX_CONTEXT, ContextType, InboxService
from backend.common.exceptions import ConflictError
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.common.recruiting_enums import ApplicationStage, JobKind, RecruitingEvent
from backend.communication.inbox_access import visible_services
from backend.communication.inbox_rows import can_assign, facts_of, reply_contact
from backend.notification_management.event_recorder import record_event

_ASSIGNED_CONTEXTS = frozenset({ContextType.ACTIVITY, ContextType.APPLICATION})


def reply_subject(subject: str | None) -> str:
    """``Re: <subject>``, unless the subject already says so."""
    subject = (subject or "").strip()
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}".strip()


def pick_application(applications):
    """The application an Assign attaches to among one person's for one job.

    The live one when there is one, else the newest (all were rejected).

    Args:
        applications (list[ApplicationEntity]): One person's, one job's.

    Returns:
        ApplicationEntity | None: The pick, or None for an empty list.
    """
    newest_first = sorted(applications, key=lambda a: a.application_id, reverse=True)
    for application in newest_first:
        if application.stage != ApplicationStage.REJECTED:
            return application
    return newest_first[0] if newest_first else None


class InboxThreadWrites:
    """The write half of ``InboxThreadService``; relies on its repositories."""

    async def reply(self, session, user, thread_id, body, last_seen_message_id):
        """Send a reply from the thread's reply address. Commits.

        Application threads reply from the recruiting sender and add an
        ``EMAIL_SENT`` entry to the application's timeline; every other
        thread replies from its service's alias.

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
        is_application = thread.context_type == ContextType.APPLICATION
        if is_application:
            alias = self._conversation.sender_address
        else:
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
        if is_application:
            await record_event(
                session,
                subject_type="application",
                subject_id=thread.context_id,
                actor_id=user.user_id,
                event_type=RecruitingEvent.EMAIL_SENT,
                details={
                    "subject": subject,
                    "to": [contact],
                    "threadId": thread_id,
                    "direction": "outbound",
                },
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
        self, session, user, thread_id, person_id, round_id=None, job_id=None
    ):
        """Attach a thread to a person and a Mentorship round or Recruiting job. Commits.

        A Mentorship thread takes ``round_id`` (any existing round, registered
        or not). A Recruiting thread takes ``job_id`` of an EMPLOYMENT job and
        is attached to the person's live application there, else their newest.

        Args:
            session (AsyncSession): The active DB session.
            user (UserContextDto): The viewer.
            thread_id (int): The thread.
            person_id (int): Who the thread is with.
            round_id (int | None): The round, for Mentorship.
            job_id (int | None): The job, for Recruiting.

        Returns:
            InboxThreadDetailDto: The assigned thread.

        Raises:
            ValueError: Thread not found or not visible; the thread cannot be
                assigned; the wrong kind of target; the round, person, job or
                application does not exist; the job is not EMPLOYMENT.
        """
        thread, service, facts = await self._load_for_write(session, user, thread_id)
        if not can_assign(service, facts):
            raise ValueError("This thread cannot be assigned")
        if service == InboxService.MENTORSHIP:
            if round_id is None or job_id is not None:
                raise ValueError("A Mentorship thread is assigned to a round")
            context_type, context_id = ContextType.ACTIVITY, round_id
            details = {"userId": person_id, "roundId": round_id}
            if await self._rounds.get_by_round_id(session, round_id) is None:
                raise ValueError(f"round {round_id} not found")
            if not await self._users.get_all_by_ids(session, [person_id]):
                raise ValueError(f"user {person_id} not found")
        else:
            if job_id is None or round_id is not None:
                raise ValueError("A Recruiting thread is assigned to a job")
            application = await self._application_for(session, person_id, job_id)
            context_type = ContextType.APPLICATION
            context_id = application.application_id
            details = {"userId": person_id, "applicationId": context_id}

        thread.user_id = person_id
        thread.context_type = context_type
        thread.context_id = context_id
        return await self._finish(session, user, thread, InboxEvent.ASSIGNED, details)

    async def unassign(self, session, user, thread_id):
        """Detach a thread from its person and round or application. Commits.

        Raises:
            ValueError: Thread not found or not visible, cannot be assigned,
                or is not assigned.
        """
        thread, service, facts = await self._load_for_write(session, user, thread_id)
        if not can_assign(service, facts):
            raise ValueError("This thread cannot be assigned")
        if thread.context_type not in _ASSIGNED_CONTEXTS or thread.context_id is None:
            raise ValueError("This thread is not assigned")
        key = (
            "roundId"
            if thread.context_type == ContextType.ACTIVITY
            else "applicationId"
        )
        details = {"userId": thread.user_id, key: thread.context_id}
        thread.user_id = None
        thread.context_type = INBOX_CONTEXT[service]
        thread.context_id = None
        return await self._finish(session, user, thread, InboxEvent.UNASSIGNED, details)

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

    async def _application_for(self, session, person_id, job_id):
        job = await self._jobs.get_by_job_id(session, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")
        if job.kind != JobKind.EMPLOYMENT:
            raise ValueError("Only an employment job can be assigned from the Inbox")
        applications = [
            application
            for application, _ in await self._applications.list_by_user(
                session, person_id
            )
            if application.job_id == job_id
        ]
        application = pick_application(applications)
        if application is None:
            raise ValueError(f"user {person_id} has not applied to job {job_id}")
        return application

    async def _finish(self, session, user, thread, event_type, details=None):
        await record_event(
            session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=thread.thread_id,
            actor_id=user.user_id,
            event_type=event_type,
            details=details,
        )
        await session.commit()
        return await self.get_thread(session, user, thread.thread_id)
