"""Single implementation of "needs reply" and "archived" for Inbox threads.

Functions read only ``direction``, ``inbound_kind``, ``gmail_internal_date`` and
``created_at`` from each message, in any order.
"""

from backend.common.communication_enums import EmailDirection, InboundKind


def message_time(m):
    """Our own sent mail has no Gmail internal date, so fall back to created_at."""
    return m.gmail_internal_date or m.created_at


def _latest(messages, pred):
    times = [message_time(m) for m in messages if pred(m)]
    return max(times) if times else None


def _human_inbound(m):
    return (
        m.direction == EmailDirection.INBOUND
        and (m.inbound_kind or InboundKind.HUMAN) == InboundKind.HUMAN
    )


def is_archived(messages, archived_at):
    """Archived until a human message arrives after ``archived_at``."""
    if archived_at is None:
        return False
    last_in = _latest(messages, _human_inbound)
    return last_in is None or last_in <= archived_at


def needs_reply(messages, archived_at):
    """True when the newest human inbound has no later outbound and is not archived."""
    last_in = _latest(messages, _human_inbound)
    if last_in is None:
        return False
    last_out = _latest(messages, lambda m: m.direction == EmailDirection.OUTBOUND)
    if last_out is not None and last_out >= last_in:
        return False
    return not is_archived(messages, archived_at)
