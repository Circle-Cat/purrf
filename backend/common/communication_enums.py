"""Enums for the person-anchored member-email feature.

Kept in ``common`` because email spans domains (recruiting today; activity,
employment, and broadcast later), so no single domain owns these.
"""

from enum import StrEnum


class ContextType(StrEnum):
    """The scenario a member-email thread belongs to (its context tag).

    Threads are anchored to a person (``users.user_id``); this marks which
    relationship a given thread is about, so one set of tables serves every
    email scenario. Only ``APPLICATION`` is used in the MVP; the rest are
    reserved so activity / employment / broadcast email can reuse the
    ``email_thread`` / ``email_message`` tables without a schema change.
    """

    APPLICATION = "application"
    ACTIVITY = "activity"
    EMPLOYMENT = "employment"
    BROADCAST = "broadcast"


class EmailDirection(StrEnum):
    """Which way a message travelled relative to the company account."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"
