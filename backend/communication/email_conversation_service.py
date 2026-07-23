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
- ``sync_thread`` / ``sync_context`` — pull threads back from Gmail and upsert
  any messages we do not already have (idempotent on ``gmail_message_id``),
  classifying each as OUTBOUND/INBOUND by comparing its ``From`` to the
  company sender.
"""

import asyncio
from datetime import datetime, timezone
from email.utils import parseaddr

from backend.common.communication_enums import EmailDirection
from backend.dto.email_dto import EmailMessageDto, EmailThreadDto


class EmailConversationService:
    def __init__(
        self, gmail_client, thread_repository, message_repository, sender_address
    ):
        """
        Args:
            gmail_client (GmailClient): Transport (send / read).
            thread_repository (EmailThreadRepository): Thread data access.
            message_repository (EmailMessageRepository): Message data access.
            sender_address (str): The company sender address, used to classify
                a synced message's direction.
        """
        self._gmail = gmail_client
        self._thread_repo = thread_repository
        self._message_repo = message_repository
        self._sender_address = sender_address

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
            list[EmailThreadDto]: One per thread (oldest first), each with its
                messages assembled (oldest first).
        """
        threads = await self._thread_repo.list_by_context(
            session, context_type, context_id
        )
        conversation = []
        for thread in threads:
            messages = await self._message_repo.list_by_thread(
                session, thread.thread_id
            )
            conversation.append(
                EmailThreadDto(
                    thread_id=thread.thread_id,
                    subject=thread.subject,
                    synced_at=thread.synced_at,
                    created_at=thread.created_at,
                    messages=[EmailMessageDto.model_validate(m) for m in messages],
                )
            )
        return conversation

    async def sync_context(self, session, context_type, context_id):
        """Sync every thread for one scenario (e.g. one application).

        Args:
            session (AsyncSession): The active DB session.
            context_type (str): A ``ContextType`` value.
            context_id (int | None): The scenario entity id.

        Returns:
            int: Total number of new messages persisted across the threads.
        """
        threads = await self._thread_repo.list_by_context(
            session, context_type, context_id
        )
        total = 0
        for thread in threads:
            total += await self.sync_thread(session, thread)
        return total

    async def sync_thread(self, session, thread):
        """Pull one thread from Gmail and persist any messages we lack.

        Args:
            session (AsyncSession): The active DB session.
            thread (EmailThreadEntity): The thread to sync.

        Returns:
            int: Number of new messages persisted (idempotent on
                ``gmail_message_id``, so re-syncing returns 0).
        """
        fetched = await asyncio.to_thread(
            self._gmail.get_thread, thread.gmail_thread_id
        )
        new_count = 0
        for message in fetched:
            existing = await self._message_repo.get_by_gmail_message_id(
                session, message["gmail_message_id"]
            )
            if existing is not None:
                continue
            await self._message_repo.create(
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
            new_count += 1
        await self._thread_repo.mark_synced(session, thread.thread_id)
        return new_count

    def _direction_of(self, from_address):
        """OUTBOUND when the message is from our sender, INBOUND otherwise."""
        address = parseaddr(from_address or "")[1].lower()
        if address and address == (self._sender_address or "").lower():
            return EmailDirection.OUTBOUND
        return EmailDirection.INBOUND

    @staticmethod
    def _parse_internal_date(value):
        """Convert Gmail's epoch-millis string to a tz-aware datetime (or None)."""
        if not value:
            return None
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
