"""Pure derivations for Inbox rows: who the thread is with, its flags, search, order.

Needs reply and archived come from ``inbox_state``; everything here only reads
a thread and its messages, so the service can batch the queries around it.
"""

from dataclasses import dataclass
from datetime import datetime
from email.utils import getaddresses, parseaddr

from backend.common.communication_enums import (
    EmailDirection,
    InboundKind,
    InboxService,
)
from backend.communication.inbox_state import (
    is_archived,
    is_bounce,
    is_human_inbound,
    message_time,
    needs_reply,
)


def address_of(raw: str | None) -> str | None:
    """The bare, lower-cased address of one header value such as ``"A" <a@x.com>``."""
    if not raw:
        return None
    return parseaddr(raw)[1].strip().lower() or None


def _first_address(raw: str | None) -> str | None:
    if not raw:
        return None
    for _, address in getaddresses([raw]):
        if address.strip():
            return address.strip().lower()
    return None


def inbound_kind_of(m) -> str | None:
    """An inbound message's kind, as ``inbox_state`` judges it; None for outbound."""
    if is_bounce(m):
        return InboundKind.BOUNCE
    if is_human_inbound(m):
        return InboundKind.HUMAN
    return m.inbound_kind if m.direction == EmailDirection.INBOUND else None


def _contact_of(ordered) -> str | None:
    for m in ordered:
        if is_human_inbound(m) and (address := address_of(m.from_address)):
            return address
    for m in ordered:
        if m.direction == EmailDirection.OUTBOUND:
            return _first_address(m.to_addresses)
    return None


def reply_contact(ordered) -> str | None:
    """Who a reply goes to: the newest human sender, else our first recipient.

    Args:
        ordered (list[EmailMessageEntity]): Messages, oldest first.
    """
    for m in reversed(ordered):
        if is_human_inbound(m) and (address := address_of(m.from_address)):
            return address
    for m in ordered:
        if m.direction == EmailDirection.OUTBOUND:
            return _first_address(m.to_addresses)
    return None


def _machine_tag(ordered) -> str | None:
    inbound = [m for m in ordered if m.direction == EmailDirection.INBOUND]
    if not inbound:
        return None
    kind = inbound_kind_of(inbound[-1])
    return kind if kind in (InboundKind.AUTO_REPLY, InboundKind.BOUNCE) else None


def _open_bounce_to(ordered, contact: str | None) -> str | None:
    bounces = [m for m in ordered if is_bounce(m)]
    if not bounces:
        return None
    bounce = bounces[-1]
    outbound = [m for m in ordered if m.direction == EmailDirection.OUTBOUND]
    if outbound and message_time(outbound[-1]) > message_time(bounce):
        return None
    return (bounce.failed_recipients or "").strip() or contact


@dataclass(frozen=True)
class ThreadFacts:
    """What one thread's messages say, computed once per request."""

    ordered: list
    contact: str | None
    tracked: bool
    needs_reply: bool
    archived: bool
    last_activity_at: datetime
    last_human_inbound_at: datetime | None
    snippet: str | None
    machine_tag: str | None
    open_bounce_to: str | None

    @property
    def sort_time(self) -> datetime:
        """Needs-reply threads sort by their latest human mail, others by activity."""
        if self.needs_reply and self.last_human_inbound_at is not None:
            return self.last_human_inbound_at
        return self.last_activity_at


def facts_of(thread, messages) -> ThreadFacts:
    """Derive a thread's facts from its messages, in any order.

    The contact is the first human sender, else the first recipient of our
    first outbound mail. A thread is tracked when we wrote first.

    Args:
        thread (EmailThreadEntity): The thread.
        messages (list[EmailMessageEntity]): All of its messages.

    Returns:
        ThreadFacts: The derived facts; messages ordered oldest first.
    """
    ordered = sorted(messages, key=lambda m: (message_time(m), m.message_id))
    human = [message_time(m) for m in ordered if is_human_inbound(m)]
    contact = _contact_of(ordered)
    return ThreadFacts(
        ordered=ordered,
        contact=contact,
        tracked=bool(ordered) and ordered[0].direction == EmailDirection.OUTBOUND,
        needs_reply=needs_reply(ordered, thread.archived_at),
        archived=is_archived(ordered, thread.archived_at),
        last_activity_at=(
            max(message_time(m) for m in ordered) if ordered else thread.created_at
        ),
        last_human_inbound_at=max(human) if human else None,
        snippet=ordered[-1].snippet if ordered else None,
        machine_tag=_machine_tag(ordered),
        open_bounce_to=_open_bounce_to(ordered, contact),
    )


def can_assign(service: InboxService, facts: ThreadFacts) -> bool:
    """Inquiries are never about one person, and a tracked thread keeps its owner."""
    return service != InboxService.INQUIRIES and not facts.tracked


def matches_search(
    q: str | None,
    person_name: str | None,
    sender: str | None,
    subject: str | None,
) -> bool:
    """Whether a thread matches the search box: a case-insensitive substring
    of the person's name, the sender address or the subject."""
    needle = (q or "").strip().lower()
    if not needle:
        return True
    return any(
        needle in (value or "").lower() for value in (person_name, sender, subject)
    )
