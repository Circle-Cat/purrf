"""Enums for the person-anchored member-email feature.

Kept in ``common`` because email spans domains (recruiting today; activity,
employment, and broadcast later), so no single domain owns these.
"""

from enum import StrEnum


class ContextType(StrEnum):
    """The scenario a member-email thread belongs to (its context tag).

    Threads are anchored to a person (``users.user_id``); this marks which
    relationship a given thread is about, so one set of tables serves every
    email scenario. APPLICATION tags application threads; the *_INBOX members
    tag threads received through a service's Inbox; ACTIVITY, EMPLOYMENT, and
    BROADCAST are reserved for future scenarios. All share the same
    ``email_thread`` / ``email_message`` tables.
    """

    APPLICATION = "application"
    ACTIVITY = "activity"
    EMPLOYMENT = "employment"
    BROADCAST = "broadcast"
    MENTORSHIP_INBOX = "mentorship_inbox"
    RECRUITING_INBOX = "recruiting_inbox"
    INQUIRIES_INBOX = "inquiries_inbox"


class EmailDirection(StrEnum):
    """Which way a message travelled relative to the company account."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"


class InboundKind(StrEnum):
    """Who wrote an inbound message. Only human mail can make a thread need a reply."""

    HUMAN = "human"
    AUTO_REPLY = "auto_reply"
    BOUNCE = "bounce"


class InboxService(StrEnum):
    """The service an Inbox thread belongs to; each has one alias and one permission."""

    MENTORSHIP = "mentorship"
    RECRUITING = "recruiting"
    INQUIRIES = "inquiries"


INBOX_CONTEXT: dict[InboxService, ContextType] = {
    InboxService.MENTORSHIP: ContextType.MENTORSHIP_INBOX,
    InboxService.RECRUITING: ContextType.RECRUITING_INBOX,
    InboxService.INQUIRIES: ContextType.INQUIRIES_INBOX,
}
