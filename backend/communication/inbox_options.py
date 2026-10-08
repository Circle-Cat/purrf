"""Inbox reads that are not about one thread's content: attachments, Assign choices, people."""

import asyncio
import re

from backend.common.communication_enums import InboxService
from backend.common.name_utils import display_name_of
from backend.common.recruiting_enums import JobKind
from backend.communication.inbox_rows import can_assign, facts_of
from backend.dto.inbox_dto import (
    AssignOptionsDto,
    InboxApplicationOptionDto,
    InboxJobOptionDto,
    InboxRoundOptionDto,
    PersonDto,
)

_MAX_PEOPLE = 20
_ID_QUERY = re.compile(r"^#?(\d+)$")


class InboxThreadOptions:
    """Attachment download, Assign choices and people search of ``InboxThreadService``."""

    async def download_attachment(
        self, session, user, thread_id, message_id, attachment_index
    ):
        """Fetch one attachment of one message of a visible thread.

        Args:
            session (AsyncSession): The active DB session.
            user (UserContextDto): The viewer.
            thread_id (int): The thread.
            message_id (int): A message of that thread.
            attachment_index (int): Position in the message's attachments.

        Returns:
            tuple[bytes, str]: The content and the file name.

        Raises:
            ValueError: Thread not found or not visible; or the message is not
                in the thread or has no attachment at that index.
        """
        await self._load_visible(session, user, thread_id, inbox_only=False)
        messages = await self._messages.list_by_thread(session, thread_id)
        message = next((m for m in messages if m.message_id == message_id), None)
        attachments = (message.attachments or []) if message else []
        if message is None or not 0 <= attachment_index < len(attachments):
            raise ValueError("attachment not found")
        entry = attachments[attachment_index]
        content = await asyncio.to_thread(
            self._gmail.get_attachment,
            message.gmail_message_id,
            entry["gmailAttachmentId"],
        )
        return content, entry.get("name") or "attachment"

    async def assign_options(self, session, user, thread_id, person_id):
        """What a thread could be assigned to for one person.

        Mentorship lists every round, marking the current one and the rounds
        the person registered for. Recruiting lists every employment job the
        person applied to with all of their applications there, rejected ones
        included, newest first; jobs come in order of their newest application.

        Args:
            session (AsyncSession): The active DB session.
            user (UserContextDto): The viewer.
            thread_id (int): The thread.
            person_id (int): The person to assign.

        Returns:
            AssignOptionsDto: ``rounds`` or ``jobs``.

        Raises:
            ValueError: Thread not found or not visible, or cannot be assigned.
        """
        thread, service = await self._load_visible(session, user, thread_id)
        messages = await self._messages.list_by_thread(session, thread_id)
        if not can_assign(service, facts_of(thread, messages)):
            raise ValueError("This thread cannot be assigned")
        if service == InboxService.MENTORSHIP:
            return AssignOptionsDto(
                rounds=await self._round_options(session, person_id)
            )
        return AssignOptionsDto(jobs=await self._job_options(session, person_id))

    async def _round_options(self, session, person_id):
        rounds = await self._rounds.get_all_rounds(session)
        current = (await self._rounds_service.get_round_slots(session)).active_round_id
        options = []
        for r in rounds:
            registered = await self._participants.get_by_user_id_and_round_id(
                session, person_id, r.round_id
            )
            options.append(
                InboxRoundOptionDto(
                    round_id=r.round_id,
                    name=r.name,
                    current=r.round_id == current,
                    registered=registered is not None,
                )
            )
        return options

    async def _job_options(self, session, person_id):
        by_job = {}
        for application, job in await self._applications.list_by_user(
            session, person_id
        ):
            if job.kind == JobKind.EMPLOYMENT:
                by_job.setdefault(job.job_id, (job, []))[1].append(application)
        options = []
        for job, applications in by_job.values():
            applications.sort(key=lambda a: a.application_id, reverse=True)
            options.append(
                InboxJobOptionDto(
                    job_id=job.job_id,
                    title=job.title,
                    applications=[
                        InboxApplicationOptionDto(
                            application_id=a.application_id,
                            stage=a.stage.value,
                            applied_at=a.created_datetime,
                        )
                        for a in applications
                    ],
                )
            )
        options.sort(key=lambda o: o.applications[0].application_id, reverse=True)
        return options

    async def search_people(self, session, q):
        """Find users by name or address for the Assign dialog, at most 20.

        A query of digits (optionally ``#``-prefixed) also looks up that exact
        user id and puts it first. Blocked users are left out. The route is
        limited to people who may assign threads.

        Args:
            session (AsyncSession): The active DB session.
            q (str): The search text.

        Returns:
            list[PersonDto]: Matches with their contact address.
        """
        q = (q or "").strip()
        if not q:
            return []
        rows, _ = await self._users.list_users(
            session, search=q, limit=_MAX_PEOPLE, is_blocked=False
        )
        found = [row[0] for row in rows]
        match = _ID_QUERY.match(q)
        if match:
            exact = await self._users.get_user_by_user_id(session, int(match.group(1)))
            if exact is not None and not exact.is_blocked:
                found = [exact] + [u for u in found if u.user_id != exact.user_id]
        found = found[:_MAX_PEOPLE]
        emails = await self._user_emails.get_contact_emails_by_user_ids(
            session, [u.user_id for u in found]
        )
        return [
            PersonDto(
                user_id=u.user_id,
                name=display_name_of(u),
                email=emails.get(u.user_id),
            )
            for u in found
        ]
