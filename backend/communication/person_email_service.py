"""Email with one person in one context, for any domain.

A domain checks who may read or write, then hands this service an
``EmailPolicy``: whose mail it is, the context it is filed under, the address
it goes out as, and the addresses that may be written to. Write methods do not
commit; the domain records its own events and commits.
"""

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from backend.common.communication_enums import ContextType, EmailDirection
from backend.common.exceptions import ConflictError, NotFoundError
from backend.common.html_text import text_to_html
from backend.common.name_utils import display_name_of
from backend.communication.email_replies import reply_contact, reply_subject
from backend.dto.email_dto import (
    SUBJECT_MAX_LENGTH,
    TEXT_BODY_MAX_LENGTH,
    EmailConversationDto,
    EmailRecipientOptionDto,
)


class BodyFormat(StrEnum):
    """``text`` is escaped and kept as typed; ``rich`` is HTML from an editor."""

    TEXT = "text"
    RICH = "rich"


@dataclass(frozen=True)
class EmailPolicy:
    """What a domain allows for one person in one context, already resolved.

    Built per request by the domain after its own access checks.
    """

    user_id: int
    context_type: ContextType
    context_id: int | None
    sender_address: str | None
    may_send: bool
    body_format: BodyFormat
    recipient_options: tuple[EmailRecipientOptionDto, ...] = ()
    default_to: str | None = None

    @property
    def can_send(self) -> bool:
        """The viewer may send, and this environment has an address to send as."""
        return self.may_send and self.sender_address is not None


@dataclass(frozen=True)
class PersonAddress:
    """One address on a person's account; domains decide what to call it."""

    address: str
    is_primary: bool


def recipient_options(addresses, default) -> list[EmailRecipientOptionDto]:
    """The compose choices: ``default`` first, then every other address once.

    The only place option labels are set, keyed by the explicit default and
    never by an earlier label.

    Args:
        addresses (list[str]): The person's addresses, in display order.
        default (str | None): The preselected address; offered even when it
            is not among ``addresses``.

    Returns:
        list[EmailRecipientOptionDto]: ``default`` labelled ``Primary contact``,
            the rest ``Alternative``; case-insensitive duplicates dropped.
    """
    default_key = (default or "").strip().lower()
    options = []
    seen = set()
    for raw in ([default] if default_key else []) + list(addresses):
        address = (raw or "").strip()
        key = address.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        options.append(
            EmailRecipientOptionDto(
                address=address,
                label="Primary contact" if key == default_key else "Alternative",
            )
        )
    return options


_NO_SENDER = "This environment has no address to send these emails from"
_NO_WRITE = "You cannot send email here"


def _bodies(body_format: BodyFormat, body: str) -> tuple[str, str | None]:
    """The HTML to send and the plain text to keep."""
    if body_format == BodyFormat.TEXT:
        return text_to_html(body), body
    return body, None


def _clean_subject(subject: str | None) -> str:
    """One line, so nothing typed can reach another header."""
    cleaned = " ".join((subject or "").split())
    if not cleaned:
        raise ValueError("The subject is required")
    if len(cleaned) > SUBJECT_MAX_LENGTH:
        raise ValueError(f"The subject is longer than {SUBJECT_MAX_LENGTH} characters")
    return cleaned


def _check_body(body_format: BodyFormat, body: str | None) -> None:
    if not (body or "").strip():
        raise ValueError("The message is empty")
    if body_format == BodyFormat.TEXT and len(body) > TEXT_BODY_MAX_LENGTH:
        raise ValueError(
            f"The message is longer than {TEXT_BODY_MAX_LENGTH} characters"
        )


def _check_may_send(policy: EmailPolicy) -> None:
    if policy.sender_address is None:
        raise ValueError(_NO_SENDER)
    if not policy.may_send:
        raise ValueError(_NO_WRITE)


def _resolve_recipients(policy: EmailPolicy, to) -> list[str]:
    """The offered addresses ``to`` names, as offered, in order, once each."""
    offered = {o.address.lower(): o.address for o in policy.recipient_options}
    resolved = []
    for raw in to or []:
        address = offered.get((raw or "").strip().lower())
        if address is None:
            raise ValueError(
                f"{raw!r} is not an address this person can be written to at"
            )
        if address not in resolved:
            resolved.append(address)
    if not resolved:
        raise ValueError("Choose at least one recipient")
    return resolved


class PersonEmailService:
    def __init__(
        self,
        conversation_service,
        thread_repository,
        message_repository,
        users_repository,
        user_emails_repository,
        context_registry,
        gmail_client,
    ):
        """
        Args:
            conversation_service (EmailConversationService): Sends, lists, syncs.
            thread_repository (EmailThreadRepository): Loads threads.
            message_repository (EmailMessageRepository): Loads messages.
            users_repository (UsersRepository): Names who sent through Purrf.
            user_emails_repository (UserEmailsRepository): A person's addresses.
            context_registry (EmailContextRegistry): The sync handler of each context.
            gmail_client (GmailClient): Downloads attachments.
        """
        self._conversation = conversation_service
        self._threads = thread_repository
        self._messages = message_repository
        self._users = users_repository
        self._user_emails = user_emails_repository
        self._registry = context_registry
        self._gmail = gmail_client

    @property
    def default_sender_address(self) -> str:
        """The address the conversation service sends as when none is named."""
        return self._conversation.sender_address

    async def person_email_addresses(self, session, user_id: int) -> list[PersonAddress]:
        """Every address on the person's account, the primary first. No labels.

        Pending addresses are included: they are on the account the way the
        participant page shows them, and imported people only have those.

        Args:
            session (AsyncSession): The active DB session.
            user_id (int): The person.

        Returns:
            list[PersonAddress]: Primary, then the others by when they were
                added; case-insensitive duplicates dropped.
        """
        rows = await self._user_emails.list_by_user_id(session, user_id)
        addresses = []
        seen = set()
        for row in sorted(rows, key=lambda r: (not r.is_primary, r.email_id)):
            address = (row.email or "").strip()
            if not address or address.lower() in seen:
                continue
            seen.add(address.lower())
            addresses.append(
                PersonAddress(address=address, is_primary=bool(row.is_primary))
            )
        return addresses

    async def conversation(self, session, policy: EmailPolicy) -> EmailConversationDto:
        """Every thread with the policy's person in its context. Pure DB read.

        Args:
            session (AsyncSession): The active DB session.
            policy (EmailPolicy): Whose mail, and what the viewer may do.

        Returns:
            EmailConversationDto: Threads newest first, with sender names, and
                the compose choices of the policy.
        """
        threads = await self._conversation.list_conversation(
            session, policy.context_type, policy.context_id, user_id=policy.user_id
        )
        await self._name_senders(session, threads)
        for thread in threads:
            thread.reply_alias = policy.sender_address
        return EmailConversationDto(
            threads=threads,
            default_to=policy.default_to,
            can_send=policy.can_send,
            sender_address=policy.sender_address,
            recipient_options=list(policy.recipient_options),
        )

    async def _name_senders(self, session, threads) -> None:
        sender_ids = sorted({
            m.sent_by_user_id
            for t in threads
            for m in t.messages
            if m.sent_by_user_id is not None
        })
        if not sender_ids:
            return
        users = await self._users.get_all_by_ids(session, sender_ids)
        names = {u.user_id: display_name_of(u) or None for u in users}
        for thread in threads:
            for message in thread.messages:
                message.sent_by_name = names.get(message.sent_by_user_id)

    async def send_new(
        self, session, policy: EmailPolicy, *, sender_user_id, to, subject, body
    ):
        """Send a new email, which opens a new thread. Does not commit.

        Args:
            session (AsyncSession): The active DB session.
            policy (EmailPolicy): Whose mail, and what the viewer may do.
            sender_user_id (int | None): Who pressed send.
            to (list[str]): Chosen addresses; each must be one of the options.
            subject (str): Collapsed to one line.
            body (str): Plain text or HTML, as the policy's format says.

        Returns:
            EmailMessageEntity: The stored outbound message.

        Raises:
            ValueError: No sender address, no right to send, a recipient that
                is not offered, or a missing or overlong subject or body.
            RateLimitedError / RuntimeError: From Gmail; nothing is stored.
        """
        _check_may_send(policy)
        subject = _clean_subject(subject)
        _check_body(policy.body_format, body)
        recipients = _resolve_recipients(policy, to)
        return await self._send(
            session,
            (policy.user_id, policy.context_type, policy.context_id),
            to=recipients,
            subject=subject,
            body=body,
            body_format=policy.body_format,
            sender_address=policy.sender_address,
            sender_user_id=sender_user_id,
        )

    async def reply(
        self,
        session,
        policy: EmailPolicy,
        *,
        sender_user_id,
        thread_id,
        body,
        last_seen_message_id,
    ):
        """Reply in one of the policy's threads. Does not commit.

        Raises:
            NotFoundError: The thread is missing or not the policy's.
            ValueError: No right to send, an empty or overlong body, no sender
                address, or nobody to reply to.
            ConflictError: ``THREAD_CHANGED`` when a newer message arrived.
        """
        thread = await self._owned_thread(session, policy, thread_id)
        if not policy.may_send:
            raise ValueError(_NO_WRITE)
        _check_body(policy.body_format, body)
        return await self.reply_into(
            session,
            thread,
            body=body,
            body_format=policy.body_format,
            last_seen_message_id=last_seen_message_id,
            sender_address=policy.sender_address,
            sender_user_id=sender_user_id,
        )

    async def reply_into(
        self,
        session,
        thread,
        *,
        body,
        body_format: BodyFormat,
        last_seen_message_id,
        sender_address,
        sender_user_id,
    ):
        """Send a reply in ``thread`` to whoever a reply goes to. Does not commit.

        Shared by the Inbox, which checks the thread's visibility itself.

        Args:
            session (AsyncSession): The active DB session.
            thread (EmailThreadEntity): The thread.
            body (str): Plain text or HTML, as ``body_format`` says.
            body_format (BodyFormat): How to send ``body``.
            last_seen_message_id (int | None): The newest message the sender saw.
            sender_address (str | None): The address to send as.
            sender_user_id (int | None): Who pressed send.

        Returns:
            EmailMessageEntity: The stored reply.

        Raises:
            ConflictError: ``THREAD_CHANGED`` when a newer message arrived.
            ValueError: No sender address, or nobody to reply to.
        """
        messages = await self._messages.list_by_thread(session, thread.thread_id)
        if messages and messages[-1].message_id != last_seen_message_id:
            raise ConflictError(
                "This thread has new messages. Read them before sending.",
                code="THREAD_CHANGED",
            )
        if sender_address is None:
            raise ValueError(_NO_SENDER)
        contact = reply_contact(messages)
        if contact is None:
            raise ValueError("This thread has nobody to reply to")
        return await self._send(
            session,
            (thread.user_id, thread.context_type, thread.context_id),
            to=[contact],
            subject=reply_subject(thread.subject),
            body=body,
            body_format=body_format,
            sender_address=sender_address,
            sender_user_id=sender_user_id,
            thread_id=thread.thread_id,
        )

    async def _owned_thread(self, session, policy: EmailPolicy, thread_id):
        thread = await self._threads.get(session, thread_id)
        if thread is None or (
            thread.user_id,
            thread.context_type,
            thread.context_id,
        ) != (policy.user_id, policy.context_type, policy.context_id):
            raise NotFoundError(f"Email thread {thread_id} not found")
        return thread

    async def refresh(self, session, policy: EmailPolicy) -> int:
        """Pull the person's threads in this context from Gmail. Does not commit.

        Each thread goes through the handler registered for its context, so
        mail found here has the same consequences as mail a Gmail push brings.

        Args:
            session (AsyncSession): The active DB session.
            policy (EmailPolicy): Whose threads.

        Returns:
            int: Inbound messages this refresh stored.

        Raises:
            ValueError: A thread's context has no registered handler.
            RateLimitedError / RuntimeError: From Gmail.
        """
        threads = await self._threads.list_by_person_context(
            session, policy.user_id, policy.context_type, policy.context_id
        )
        before = await self._inbound_ids(session, threads)
        for thread in threads:
            handler = self._registry.get(thread.context_type)
            if handler is None:
                raise ValueError(f"No email handler for {thread.context_type!r}")
            await handler.sync_tracked_thread(session, thread)
        return len(await self._inbound_ids(session, threads) - before)

    async def _inbound_ids(self, session, threads) -> set[int]:
        ids = set()
        for thread in threads:
            for message in await self._messages.list_by_thread(session, thread.thread_id):
                if message.direction == EmailDirection.INBOUND:
                    ids.add(message.message_id)
        return ids

    async def read_attachment(
        self, session, policy: EmailPolicy, message_id: int, index: int
    ) -> tuple[bytes, str]:
        """One attachment of a message in one of the policy's threads.

        Raises:
            NotFoundError: The message is missing or not in the policy's threads.
            ValueError: ``attachment not found`` for a bad index or entry.
        """
        message = await self._messages.get(session, message_id)
        try:
            if message is None:
                raise NotFoundError
            await self._owned_thread(session, policy, message.thread_id)
        except NotFoundError:
            raise NotFoundError(f"Email message {message_id} not found") from None
        return await self.download_attachment(message, index)

    async def download_attachment(self, message, index: int) -> tuple[bytes, str]:
        """Fetch one stored attachment of ``message`` from Gmail.

        Args:
            message (EmailMessageEntity): A message the caller may read.
            index (int): Position in ``message.attachments``.

        Returns:
            tuple[bytes, str]: The content and the file name.

        Raises:
            ValueError: ``attachment not found`` for an index out of range or
                an entry without a Gmail attachment id.
        """
        attachments = message.attachments or []
        if not 0 <= index < len(attachments):
            raise ValueError("attachment not found")
        entry = attachments[index]
        gmail_attachment_id = (
            entry.get("gmailAttachmentId") if isinstance(entry, dict) else None
        )
        if not gmail_attachment_id:
            raise ValueError("attachment not found")
        content = await asyncio.to_thread(
            self._gmail.get_attachment, message.gmail_message_id, gmail_attachment_id
        )
        return content, entry.get("name") or entry.get("filename") or "attachment"

    async def _send(
        self,
        session,
        person_context,
        *,
        to,
        subject,
        body,
        body_format,
        sender_address,
        sender_user_id,
        thread_id=None,
    ):
        """Send through Gmail; ``thread_id`` is left out for a new thread."""
        user_id, context_type, context_id = person_context
        html, text = _bodies(body_format, body)
        extra = {} if thread_id is None else {"thread_id": thread_id}
        return await self._conversation.send(
            session,
            user_id=user_id,
            context_type=context_type,
            context_id=context_id,
            to=to,
            subject=subject,
            body=html,
            sender_user_id=sender_user_id,
            sender_address=sender_address,
            body_text=text,
            **extra,
        )
