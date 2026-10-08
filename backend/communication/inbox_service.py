"""The Inbox: mail threads others started that are not assigned yet, filtered by permission.

A thread we started never shows here, and an assigned one leaves: both are
read where they belong (an application, a round).
"""

from dataclasses import dataclass, field

from backend.common.communication_enums import INBOX_CONTEXT, InboxService
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.common.name_utils import display_name_of
from backend.communication.inbox_access import visible_services
from backend.communication.inbox_rows import (
    ThreadFacts,
    can_assign,
    facts_of,
    inbound_kind_of,
    matches_search,
)
from backend.communication.inbox_options import InboxThreadOptions
from backend.communication.inbox_writes import InboxThreadWrites
from backend.communication.inbox_state import message_time
from backend.dto.inbox_dto import (
    InboxAttachmentDto,
    InboxCountsDto,
    InboxListDto,
    InboxMessageDto,
    InboxOpenBounceDto,
    InboxPersonDto,
    InboxQueryDto,
    InboxServiceCountDto,
    InboxThreadDetailDto,
    InboxThreadRowDto,
)

_INBOX_CONTEXTS = frozenset(INBOX_CONTEXT.values())


@dataclass(frozen=True)
class _Item:
    thread: object
    service: InboxService
    facts: ThreadFacts


@dataclass
class _Lookups:
    users: dict = field(default_factory=dict)
    matched: dict = field(default_factory=dict)
    moves: dict = field(default_factory=dict)


def _person_name(user, service: InboxService) -> str:
    # A recruiting thread is with a candidate, who is named by legal name.
    if service == InboxService.RECRUITING:
        return f"{user.first_name or ''} {user.last_name or ''}".strip()
    return display_name_of(user)


class InboxThreadService(InboxThreadWrites, InboxThreadOptions):
    """Reads and acts on Inbox threads; each call checks the thread's service.

    The write side (reply, archive, assign, move) lives in ``InboxThreadWrites``.
    """

    def __init__(
        self,
        thread_repository,
        message_repository,
        user_emails_repository,
        users_repository,
        application_repository,
        round_repository,
        event_repository,
        thread_service_resolver,
        conversation_service,
        aliases,
        gmail_client,
        round_participants_repository,
        rounds_service,
    ):
        """
        Args:
            thread_repository (EmailThreadRepository): Loads threads.
            message_repository (EmailMessageRepository): Loads messages.
            user_emails_repository (UserEmailsRepository): Matches senders to users.
            users_repository (UsersRepository): Names people.
            application_repository (ApplicationRepository): A person's
                applications, for Assign.
            round_repository (MentorshipRoundRepository): Names and finds rounds.
            event_repository (EventRepository): Finds the last move.
            thread_service_resolver (ThreadServiceResolver): A thread's service.
            conversation_service (EmailConversationService): Sends replies.
            aliases (InboxAliases): The reply address of each service.
            gmail_client (GmailClient): Downloads attachments.
            round_participants_repository (MentorshipRoundParticipantsRepository):
                Tells whether a person registered for a round.
            rounds_service (RoundsService): Names the current round.
        """
        self._threads = thread_repository
        self._messages = message_repository
        self._user_emails = user_emails_repository
        self._users = users_repository
        self._applications = application_repository
        self._rounds = round_repository
        self._events = event_repository
        self._resolver = thread_service_resolver
        self._conversation = conversation_service
        self._aliases = aliases
        self._gmail = gmail_client
        self._participants = round_participants_repository
        self._rounds_service = rounds_service

    async def list_threads(self, session, user, query: InboxQueryDto) -> InboxListDto:
        """The threads the viewer may see, filtered, searched and ordered.

        Threads that need a reply come first, newest human mail first; the
        rest follow by latest activity. Counts cover the selected service (or
        every visible one) without archived threads and ignore ``q``.

        Args:
            session (AsyncSession): The active DB session.
            user (UserContextDto): The viewer.
            query (InboxQueryDto): Filters and search.

        Returns:
            InboxListDto: Rows, counts and per-service Needs reply counts.
        """
        services = visible_services(user)
        items = await self._load_items(session, services)
        lookups = await self._lookups(session, items)
        rows = [(item, self._row(item, lookups)) for item in items]

        scoped = [
            (item, row)
            for item, row in rows
            if query.service is None or row.service == query.service
        ]
        live = [row for _, row in scoped if not row.archived]
        shown = [
            (item, row)
            for item, row in scoped
            if (query.archived or not row.archived)
            and (not query.needs_reply or row.needs_reply)
            and matches_search(
                query.q,
                row.person.user_id if row.person else None,
                row.person.name if row.person else None,
                row.sender,
                row.subject,
            )
        ]
        shown.sort(
            key=lambda pair: (
                pair[1].needs_reply,
                pair[0].facts.sort_time,
                pair[1].thread_id,
            ),
            reverse=True,
        )
        return InboxListDto(
            threads=[row for _, row in shown],
            counts=InboxCountsDto(
                needs_reply=sum(row.needs_reply for row in live),
            ),
            services=[
                InboxServiceCountDto(
                    key=service,
                    needs_reply=sum(
                        row.needs_reply for _, row in rows if row.service == service
                    ),
                )
                for service in services
            ],
        )

    async def count_needs_reply(self, session, user) -> int:
        """How many visible threads need a reply, across every visible service.

        Args:
            session (AsyncSession): The active DB session.
            user (UserContextDto): The viewer.

        Returns:
            int: The count for the sidebar badge.
        """
        items = await self._load_items(session, visible_services(user))
        return sum(item.facts.needs_reply for item in items)

    async def get_thread(self, session, user, thread_id: int) -> InboxThreadDetailDto:
        """One thread with its messages and what the viewer can do with it.

        Args:
            session (AsyncSession): The active DB session.
            user (UserContextDto): The viewer.
            thread_id (int): The thread.

        Returns:
            InboxThreadDetailDto: The thread.

        Raises:
            ValueError: If the thread is missing or not visible to the viewer.
        """
        thread, service = await self._load_visible(session, user, thread_id)
        messages = await self._messages.list_by_thread(session, thread_id)
        item = _Item(thread, service, facts_of(thread, messages))
        senders = {m.sent_by_user_id for m in messages if m.sent_by_user_id}
        lookups = await self._lookups(session, [item], extra_user_ids=senders)
        row = self._row(item, lookups)
        facts = item.facts
        move = lookups.moves.get(thread_id)
        return InboxThreadDetailDto(
            **dict(row),
            messages=[self._message(m, lookups.users) for m in facts.ordered],
            latest_message_id=facts.ordered[-1].message_id if facts.ordered else None,
            reply_alias=self._aliases.alias_of(service),
            can_assign=self._can_assign(item),
            open_bounce=(
                InboxOpenBounceDto(bounced_to=facts.open_bounce_to)
                if facts.open_bounce_to is not None
                else None
            ),
            moved_at=move.created_at if move else None,
        )

    async def _load_visible(self, session, user, thread_id, inbox_only=True):
        """Raises ValueError(f"thread {thread_id} not found") when missing or not visible.

        With ``inbox_only`` a thread that is not (or no longer) in the Inbox
        counts as missing.
        """
        not_found = ValueError(f"thread {thread_id} not found")
        thread = await self._threads.get(session, thread_id)
        if thread is None:
            raise not_found
        if inbox_only and thread.context_type not in _INBOX_CONTEXTS:
            raise not_found
        try:
            service = await self._resolver.service_of(session, thread)
        except ValueError:
            raise not_found from None
        if service not in visible_services(user):
            raise not_found
        return thread, service

    async def _load_items(self, session, services) -> list[_Item]:
        if not services:
            return []
        threads = await self._threads.list_by_context_types(
            session, [INBOX_CONTEXT[s] for s in services]
        )
        service_of = {context: service for service, context in INBOX_CONTEXT.items()}
        messages = await self._messages.list_by_threads(
            session, [t.thread_id for t in threads]
        )
        return [
            _Item(
                t,
                service_of[t.context_type],
                facts_of(t, messages.get(t.thread_id, [])),
            )
            for t in threads
        ]

    async def _lookups(self, session, items, extra_user_ids=()) -> _Lookups:
        """Everything rows need beyond the thread itself, one query per kind."""
        if not items:
            return _Lookups()
        senders = sorted({
            item.facts.contact
            for item in items
            if item.thread.user_id is None and item.facts.contact
        })
        matched = {
            row.email.lower(): row
            for row in await self._user_emails.list_by_emails(session, senders)
        }
        user_ids = {item.thread.user_id for item in items if item.thread.user_id}
        user_ids |= {row.user_id for row in matched.values()}
        user_ids |= set(extra_user_ids)
        users = await self._users.get_all_by_ids(session, sorted(user_ids))
        moves = await self._events.latest_by_subjects(
            session,
            INBOX_SUBJECT_TYPE,
            InboxEvent.MOVED,
            [item.thread.thread_id for item in items],
        )
        return _Lookups(
            users={u.user_id: u for u in users},
            matched=matched,
            moves=moves,
        )

    @staticmethod
    def _can_assign(item: _Item) -> bool:
        return can_assign(item.service, item.facts)

    def _row(self, item: _Item, lookups: _Lookups) -> InboxThreadRowDto:
        thread, facts = item.thread, item.facts
        person_id, matched_by = thread.user_id, None
        if person_id is None and facts.contact in lookups.matched:
            match = lookups.matched[facts.contact]
            person_id = match.user_id
            matched_by = "primary" if match.is_primary else "alternative"
        user = lookups.users.get(person_id) if person_id is not None else None
        person = (
            InboxPersonDto(user_id=user.user_id, name=_person_name(user, item.service))
            if user is not None
            else None
        )
        move = lookups.moves.get(thread.thread_id)
        moved_from = (move.details or {}).get("from") if move else None
        return InboxThreadRowDto(
            thread_id=thread.thread_id,
            service=item.service,
            subject=thread.subject,
            snippet=facts.snippet,
            last_activity_at=facts.last_activity_at,
            sender=facts.contact,
            person=person,
            matched_by=matched_by if person else None,
            needs_reply=facts.needs_reply,
            archived=facts.archived,
            no_matching_user=person is None,
            machine_tag=facts.machine_tag,
            moved_from=moved_from if moved_from in set(InboxService) else None,
        )

    @staticmethod
    def _message(m, users) -> InboxMessageDto:
        sender = users.get(m.sent_by_user_id) if m.sent_by_user_id else None
        return InboxMessageDto(
            message_id=m.message_id,
            direction=m.direction,
            from_=m.from_address,
            to=m.to_addresses,
            at=message_time(m),
            body_html=m.body_html,
            body_text=m.body_text,
            inbound_kind=inbound_kind_of(m),
            attachments=[
                InboxAttachmentDto(
                    name=entry.get("name"), size=entry.get("size"), attachment_id=index
                )
                for index, entry in enumerate(m.attachments or [])
            ],
            sent_by_name=display_name_of(sender) or None,
        )
