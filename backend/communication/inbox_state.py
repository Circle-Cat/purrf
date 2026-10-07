"""Single implementation of "needs reply" and "archived" for Inbox threads.

Functions read only ``direction``, ``inbound_kind``, ``failed_recipients``,
``gmail_internal_date`` and ``created_at`` from each message, in any order.

Inbound mail is weighed by when Purrf stored it (``created_at``), not by its
Gmail date: an Archive or a reply can only answer mail staff could already
see, so mail that syncs late still counts as new.
"""

from backend.common.communication_enums import EmailDirection, InboundKind


def message_time(m):
    """Our own sent mail has no Gmail internal date, so fall back to created_at."""
    return m.gmail_internal_date or m.created_at


def _latest(times):
    times = list(times)
    return max(times) if times else None


def is_bounce(m):
    """A delivery failure, including one stored before inbound mail was classified."""
    if m.direction != EmailDirection.INBOUND:
        return False
    if m.inbound_kind is None:
        return m.failed_recipients is not None
    return m.inbound_kind == InboundKind.BOUNCE


def is_human_inbound(m):
    """Inbound mail from a person; unclassified mail counts unless it is a bounce."""
    if m.direction != EmailDirection.INBOUND:
        return False
    if m.inbound_kind is None:
        return m.failed_recipients is None
    return m.inbound_kind == InboundKind.HUMAN


def _last_human_stored(messages):
    return _latest(m.created_at for m in messages if is_human_inbound(m))


def is_archived(messages, archived_at):
    """Archived until Purrf stores a human message after ``archived_at``."""
    if archived_at is None:
        return False
    last_in = _last_human_stored(messages)
    return last_in is None or last_in <= archived_at


def needs_reply(messages, archived_at):
    """True when no outbound follows the newest stored human inbound, and not archived."""
    last_in = _last_human_stored(messages)
    if last_in is None:
        return False
    last_out = _latest(
        message_time(m) for m in messages if m.direction == EmailDirection.OUTBOUND
    )
    if last_out is not None and last_out >= last_in:
        return False
    return not is_archived(messages, archived_at)
