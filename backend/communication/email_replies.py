"""Who a reply in an email thread goes to, and its subject, for every domain."""

from backend.common.communication_enums import EmailDirection
from backend.communication.inbox_rows import address_of, first_address
from backend.communication.inbox_state import is_human_inbound


def reply_subject(subject: str | None) -> str:
    """``Re: <subject>``, unless the subject already says so."""
    subject = (subject or "").strip()
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}".strip()


def reply_contact(ordered) -> str | None:
    """Who a reply goes to: the newest human sender, else our first recipient.

    Args:
        ordered (list[EmailMessageEntity]): Messages, oldest first.

    Returns:
        str | None: A bare lower-cased address, or None when nobody wrote.
    """
    for m in reversed(ordered):
        if is_human_inbound(m) and (address := address_of(m.from_address)):
            return address
    for m in ordered:
        if m.direction == EmailDirection.OUTBOUND:
            return first_address(m.to_addresses)
    return None
