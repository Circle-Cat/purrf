from enum import StrEnum

INBOX_SUBJECT_TYPE = "email_thread"


class InboxEvent(StrEnum):
    """Inbox thread events. Only NEEDS_REPLY and BOUNCED notify anyone; see
    backend/communication/recipient_resolvers.py."""

    NEEDS_REPLY = "inbox.needs_reply"
    BOUNCED = "inbox.bounced"
    ASSIGNED = "inbox.assigned"
    UNASSIGNED = "inbox.unassigned"
    ARCHIVED = "inbox.archived"
    UNARCHIVED = "inbox.unarchived"
    MOVED = "inbox.moved"
