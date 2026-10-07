"""Pure derivations for Inbox rows: who the thread is with, its flags, search, order.

Needs reply and archived come from ``inbox_state``; everything here only reads
a thread and its messages, so the service can batch the queries around it.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import getaddresses, parseaddr

from backend.common.communication_enums import EmailDirection, InboundKind
from backend.communication.inbox_state import is_archived, message_time, needs_reply

_USER_ID_QUERY = re.compile(r"^#?(\d+)$")


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


def _is_human_inbound(m) -> bool:
    return (
        m.direction == EmailDirection.INBOUND
        and (m.inbound_kind or InboundKind.HUMAN) == InboundKind.HUMAN
    )


def _contact_of(ordered) -> str | None:
    for m in ordered:
        if _is_human_inbound(m) and (address := address_of(m.from_address)):
            return address
    for m in ordered:
        if m.direction == EmailDirection.OUTBOUND:
            return _first_address(m.to_addresses)
    return None


def _machine_tag(ordered) -> str | None:
    inbound = [m for m in ordered if m.direction == EmailDirection.INBOUND]
    if not inbound:
        return None
    kind = inbound[-1].inbound_kind
    return kind if kind in (InboundKind.AUTO_REPLY, InboundKind.BOUNCE) else None


def _open_bounce_to(ordered, contact: str | None) -> str | None:
    bounces = [m for m in ordered if m.inbound_kind == InboundKind.BOUNCE]
    if not bounces:
        return None
    bounce = bounces[-1]
    outbound = [m for m in ordered if m.direction == EmailDirection.OUTBOUND]
    if outbound and message_time(outbound[-1]) > message_time(bounce):
        return None
    return (bounce.failed_recipients or "").strip() or contact or ""


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
    human = [message_time(m) for m in ordered if _is_human_inbound(m)]
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


def matches_search(
    q: str | None,
    person_id: int | None,
    person_name: str | None,
    sender: str | None,
    subject: str | None,
) -> bool:
    """Whether a thread matches the search box.

    Digits, optionally after one ``#``, are a user ID and match only a thread
    whose person has exactly that ID. Anything else is a case-insensitive
    substring of the person's name, the sender address or the subject.
    """
    needle = (q or "").strip().lower()
    if not needle:
        return True
    by_id = _USER_ID_QUERY.match(needle)
    if by_id:
        return person_id is not None and str(person_id) == by_id.group(1)
    return any(needle in (value or "").lower() for value in (person_name, sender, subject))
