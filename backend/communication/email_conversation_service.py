"""Person-anchored email conversation service (domain-agnostic).

Operates on ``(user_id, context_type, context_id)`` and holds **no** domain
permission logic — each caller (recruiting today; activity / employment /
broadcast later) gates access in its own thin controller and delegates here.

Two responsibilities:

- ``send`` — send a new mail or a reply through Gmail and, **only after Gmail
  confirms**, persist the outbound message (creating the thread on the first
  message). A Gmail failure raises before anything is written, so a failed
  send never leaves a phantom row. (The narrow reverse — Gmail accepted but the
  DB write then fails — is accepted for the MVP: the message went out but is
  not recorded, and a later sync will pick it up.)
- ``sync_thread`` / ``sync_context`` — pull threads back from Gmail and store
  any messages we do not already have (idempotent on ``gmail_message_id``),
  classifying each as OUTBOUND/INBOUND by comparing its ``From`` to the
  company sender. The fetch is incremental: message ids first, then bodies
  only for the ids we lack, so re-syncing an unchanged thread stays cheap no
  matter how long it has grown.
"""

import asyncio
from datetime import datetime, timezone

from backend.common.communication_enums import EmailDirection
from backend.dto.email_dto import EmailMessageDto, EmailThreadDto


def _as_utc(moment: datetime) -> datetime:
    """Make a timestamp safe to compare with any other one.

    Both timestamp columns are ``timestamptz``, so rows read from the database
    are aware; a naive value can only reach here from a fixture or a legacy
    row, and mixing the two raises. Assume UTC for those rather than crash the
    whole conversation over one message.
    """
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _latest_activity(thread: EmailThreadDto) -> datetime:
    """Sort key: when this thread last saw traffic.

    The newest message's Gmail timestamp, which is its real send time, falling
    back to our insert time for a message that has not been synced yet. A thread
    with no messages sorts by its own creation, so it cannot vanish to the
    bottom. Messages are already newest first, so the first one is the newest.
    """
    if thread.messages:
        newest = thread.messages[0]
        return _as_utc(newest.gmail_internal_date or newest.created_at)
    return _as_utc(thread.created_at)


class EmailConversationService:
    def __init__(
        self, gmail_client, thread_repository, message_repository, sender_address
    ):
        """
        Args:
            gmail_client (GmailClient): Transport (send / read).
            thread_repository (EmailThreadRepository): Thread data access.
            message_repository (EmailMessageRepository): Message data access.
            sender_address (str): The address this service sends as. One of
                the addresses the client owns; "which addresses count as ours"
                is a separate question, answered by ``owns_address``.
        """
        self._gmail = gmail_client
        self._thread_repo = thread_repository
        self._message_repo = message_repository
        self._sender_address = sender_address

    @property
    def sender_address(self):
        """The address this service sends as (so callers can keep it out of a
        default Cc list — never Cc ourselves)."""
        return self._sender_address

    async def send(
        self,
        session,
        user_id,
        context_type,
        context_id,
        to,
        cc,
        subject,
        body,
        sender_user_id,
        thread_id=None,
    ):
        """Send a message (new thread or reply) and persist it on Gmail success.

        Args:
            session (AsyncSession): The active DB session.
            user_id (int): The person the conversation is with (thread owner).
            context_type (str): A ``ContextType`` value (e.g. ``application``).
            context_id (int | None): The scenario entity id (e.g. application id).
            to (list[str]): Recipient addresses.
            cc (list[str]): Cc addresses (may be empty).
            subject (str): Subject line.
            body (str): HTML body.
            sender_user_id (int): The advancer sending this message.
            thread_id (int | None): An existing thread to reply into; ``None``
                starts a new thread.

        Returns:
            EmailMessageEntity: The persisted outbound message.

        Raises:
            ValueError: If ``thread_id`` is given but no such thread exists.
            RateLimitedError / RuntimeError: Propagated from the Gmail send.
        """
        thread = None
        gmail_thread_id = None
        in_reply_to = None
        references = None

        if thread_id is not None:
            thread = await self._thread_repo.get(session, thread_id)
            if thread is None:
                raise ValueError(f"Unknown email thread: {thread_id}")
            # A reply must stay within the context the caller claims — you
            # cannot reply into a thread that belongs to a different person or
            # scenario (prevents cross-context leakage).
            if thread.context_type != context_type or thread.context_id != context_id:
                raise ValueError(
                    f"Thread {thread_id} does not belong to the given context"
                )
            gmail_thread_id = thread.gmail_thread_id
            prior = await self._message_repo.list_by_thread(session, thread_id)
            rfc_ids = [m.rfc822_message_id for m in prior if m.rfc822_message_id]
            if rfc_ids:
                in_reply_to = rfc_ids[-1]
                references = " ".join(rfc_ids)

        sent = await asyncio.to_thread(
            self._gmail.send_message,
            to,
            cc,
            subject,
            body,
            sender=self._sender_address,
            thread_id=gmail_thread_id,
            in_reply_to=in_reply_to,
            references=references,
        )

        if thread is None:
            thread = await self._thread_repo.create(
                session,
                user_id=user_id,
                gmail_thread_id=sent["gmail_thread_id"],
                subject=subject,
                context_type=context_type,
                context_id=context_id,
            )

        return await self._message_repo.create(
            session,
            thread_id=thread.thread_id,
            gmail_message_id=sent["gmail_message_id"],
            direction=EmailDirection.OUTBOUND,
            from_address=self._sender_address,
            to_addresses=", ".join(to),
            cc_addresses=", ".join(cc) if cc else None,
            subject=subject,
            body_html=body,
            rfc822_message_id=sent["rfc822_message_id"],
            sent_by_user_id=sender_user_id,
        )

    async def list_conversation(self, session, context_type, context_id):
        """Read the stored conversation for one (context_type, context_id).

        Pure DB read (no Gmail call): opening a conversation never triggers a
        sync — that is done explicitly via ``sync_context`` (daily cron /
        manual Refresh).

        Args:
            session (AsyncSession): The active DB session.
            context_type (str): A ``ContextType`` value.
            context_id (int | None): The scenario entity id.

        Returns:
            list[EmailThreadDto]: Newest first — threads by their most recent
                message, and the messages inside each thread newest first too.
        """
        threads = await self._thread_repo.list_by_context(
            session, context_type, context_id
        )
        conversation = []
        for thread in threads:
            messages = await self._message_repo.list_by_thread(
                session, thread.thread_id
            )
            # The repository hands messages over oldest first, which is what
            # ``send`` relies on to build In-Reply-To (the last id) and a
            # References header in the chronological order RFC 5322 requires.
            # Reading is a different job, so the reversal for display lives
            # here rather than in the repository.
            conversation.append(
                EmailThreadDto(
                    thread_id=thread.thread_id,
                    subject=thread.subject,
                    synced_at=thread.synced_at,
                    created_at=thread.created_at,
                    messages=[
                        EmailMessageDto.model_validate(m) for m in reversed(messages)
                    ],
                )
            )
        conversation.sort(key=_latest_activity, reverse=True)
        return conversation

    async def sync_context(self, session, context_type, context_id):
        """Sync every thread for one scenario (e.g. one application).

        Args:
            session (AsyncSession): The active DB session.
            context_type (str): A ``ContextType`` value.
            context_id (int | None): The scenario entity id.

        Returns:
            list[EmailMessageEntity]: All messages newly persisted across the
                scenario's threads.
        """
        threads = await self._thread_repo.list_by_context(
            session, context_type, context_id
        )
        created = []
        for thread in threads:
            created.extend(await self.sync_thread(session, thread))
        return created

    async def sync_thread(self, session, thread):
        """Pull one thread from Gmail and persist any messages we lack.

        Incremental by construction: we list the thread's message ids (cheap,
        no bodies), ask the DB in one query which of them we already have, and
        fetch bodies only for the ids that are genuinely new. A re-sync of an
        unchanged thread therefore costs one Gmail call and one query, however
        long the conversation has grown.

        The bodies are fetched in batches rather than one call each, so a
        thread with a backlog costs a handful of requests instead of one per
        message. Quota is per inner call either way; what this saves is
        round-trips.

        If a message is deleted between the listing and its fetch, the fetch
        raises and the whole sync fails rather than silently persisting a
        partial thread; the retry self-heals, since the id is gone from the
        next listing.

        Args:
            session (AsyncSession): The active DB session.
            thread (EmailThreadEntity): The thread to sync.

        Returns:
            list[EmailMessageEntity]: The messages newly persisted this call,
                in Gmail's order (idempotent on ``gmail_message_id``, so
                re-syncing an unchanged thread returns []).

        Raises:
            RateLimitedError / RuntimeError: Propagated from Gmail.
        """
        gmail_ids = await asyncio.to_thread(
            self._gmail.list_thread_message_ids, thread.gmail_thread_id
        )
        known = await self._message_repo.list_gmail_message_ids_by_thread(
            session, thread.thread_id
        )
        missing = [gmail_id for gmail_id in gmail_ids if gmail_id not in known]
        # Nothing new is the common case, and it must stay free: no batch, and
        # no executor hop to discover there is nothing to fetch.
        messages = (
            await asyncio.to_thread(self._gmail.get_messages, missing)
            if missing
            else []
        )

        created = []
        for message in messages:
            entity = await self._message_repo.create(
                session,
                thread_id=thread.thread_id,
                gmail_message_id=message["gmail_message_id"],
                direction=self._direction_of(message.get("from_address")),
                from_address=message.get("from_address"),
                to_addresses=message.get("to_addresses"),
                cc_addresses=message.get("cc_addresses"),
                subject=message.get("subject"),
                body_html=message.get("html"),
                body_text=message.get("plain"),
                snippet=message.get("snippet"),
                rfc822_message_id=message.get("rfc822_message_id"),
                gmail_internal_date=self._parse_internal_date(
                    message.get("gmail_internal_date")
                ),
            )
            created.append(entity)
        await self._thread_repo.mark_synced(session, thread.thread_id)
        return created

    def _direction_of(self, from_address):
        """OUTBOUND when the message is from one of our addresses, else INBOUND.

        Deliberately not a compare against ``self._sender_address``: the mailbox
        may send as several addresses (one per service), and a message from any
        of them is still ours. The transport owns that list.
        """
        if self._gmail.owns_address(from_address):
            return EmailDirection.OUTBOUND
        return EmailDirection.INBOUND

    @staticmethod
    def _parse_internal_date(value):
        """Convert Gmail's epoch-millis string to a tz-aware datetime (or None)."""
        if not value:
            return None
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
