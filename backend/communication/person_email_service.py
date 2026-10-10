"""Email with one person in one context, for any domain.

A domain checks who may read or write, then hands this service an
``EmailPolicy``: whose mail it is, the context it is filed under, the address
it goes out as, and the addresses that may be written to. Write methods do not
commit; the domain records its own events and commits.
"""

from dataclasses import dataclass
from enum import StrEnum

from backend.common.communication_enums import ContextType
from backend.common.name_utils import display_name_of
from backend.dto.email_dto import EmailConversationDto, EmailRecipientOptionDto


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
