"""What newly synced mail on a thread calls for, for every domain that tells someone.

Two things: the thread just started needing a reply, and a send bounced.
Recording events for them is each domain's own business.
"""

from dataclasses import dataclass
from email.utils import getaddresses

from backend.common.communication_enums import EmailDirection
from backend.communication.inbox_state import (
    is_bounce,
    is_human_inbound,
    message_time,
    needs_reply,
)


@dataclass(frozen=True)
class BounceAlert:
    """One new delivery failure and the send it answers."""

    bounced_to: str
    subject: str | None
    sender_user_id: int | None


@dataclass(frozen=True)
class ThreadAlerts:
    """``needs_reply_from`` is set only when this sync tipped the thread."""

    needs_reply_from: str | None
    bounces: list[BounceAlert]


def _bounced_to(bounce, original) -> str:
    named = [a for _, a in getaddresses([bounce.failed_recipients or ""]) if a]
    if named:
        return ", ".join(named)
    return original.to_addresses or ""


def _bounce_alert(thread, messages, bounce) -> BounceAlert | None:
    bounced_at = message_time(bounce)
    earlier = [
        m
        for m in messages
        if m.direction == EmailDirection.OUTBOUND and message_time(m) <= bounced_at
    ]
    if not earlier:
        return None
    original = max(earlier, key=message_time)
    return BounceAlert(
        bounced_to=_bounced_to(bounce, original),
        subject=original.subject or thread.subject,
        sender_user_id=original.sent_by_user_id,
    )


def alerts_after_sync(thread, messages, new_messages) -> ThreadAlerts:
    """What the messages a sync just stored call for.

    Args:
        thread (EmailThreadEntity): The synced thread.
        messages (list[EmailMessageEntity]): All of its messages, new ones included.
        new_messages (list[EmailMessageEntity]): The ones this sync stored.

    Returns:
        ThreadAlerts: The newest new human sender when the thread went from
            not needing a reply to needing one, and the new bounces that
            answer one of our sends.
    """
    new_ids = {m.message_id for m in new_messages}
    before = [m for m in messages if m.message_id not in new_ids]
    bounces = [
        alert
        for alert in (
            _bounce_alert(thread, messages, m) for m in new_messages if is_bounce(m)
        )
        if alert is not None
    ]
    needs_reply_from = None
    if not needs_reply(before, thread.archived_at) and needs_reply(
        messages, thread.archived_at
    ):
        newest = max(
            (m for m in new_messages if is_human_inbound(m)), key=message_time
        )
        needs_reply_from = newest.from_address
    return ThreadAlerts(needs_reply_from=needs_reply_from, bounces=bounces)
