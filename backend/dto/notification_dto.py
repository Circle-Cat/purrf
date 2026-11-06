from datetime import datetime

from pydantic import Field

from backend.common.recruiting_enums import JobKind
from backend.dto.base_dto import BaseDto


class NotificationDto(BaseDto):
    """One row in a user's notification list.

    ``event_type`` and ``details`` come straight off the event that caused
    the row, so the reader words each kind itself -- the same pair the
    timeline renders from.
    ``job_title``/``applicant_name``/``actor_name`` are resolved display
    strings, "" (or None for actor_name) when the referenced row is missing --
    same fallback convention as MyEvaluationDto/CommentDto. A null
    ``actor_name`` means nobody did it: the rules did.

    ``subject_name`` names the person a user-scoped event is about (a block
    request's target). It is "" for every other subject type, where the person
    in the line is the applicant and ``applicant_name`` already carries them
    under the candidate naming rule.

    ``job_kind`` is the resolved posting's kind (None when the posting is
    missing), so consumers outside React can honour the display-only rule
    that an activity posting's `hired` stage reads as "Admitted".

    ``summary`` is the whole line for a posting review event, worded by the
    same phrases as its email so the two channels cannot drift; None for
    every other event, which the reader words itself.

    ``link`` is the app path where this reader acts on the notification,
    such as ``/recruiting/applications/42``, worked out per recipient by
    ``recruiting/notification_links.py``; None when there is no such page.
    """

    id: int
    event_type: str
    details: dict = {}
    job_title: str = ""
    job_kind: JobKind | None = None
    applicant_name: str = ""
    subject_name: str = ""
    actor_name: str | None = None
    created_at: datetime
    is_read: bool = False
    summary: str | None = None
    link: str | None = None


class NotificationListDto(BaseDto):
    """A page of one user's notifications plus how many of all of theirs are unread."""

    notifications: list[NotificationDto]
    unread_count: int


class UnreadCountDto(BaseDto):
    """Returned by dismiss/dismiss-all/mark-read/mark-all-read so the frontend can update the badge without a refetch."""

    unread_count: int


class MarkNotificationsReadDto(BaseDto):
    """The notifications to mark read: the bell sends the one clicked.

    Capped so one request cannot name an unbounded list.
    """

    ids: list[int] = Field(max_length=100)
