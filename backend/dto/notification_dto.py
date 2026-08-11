from datetime import datetime

from backend.common.recruiting_enums import JobKind
from backend.dto.base_dto import BaseDto


class NotificationDto(BaseDto):
    """One row in a user's notification list.

    Notifications are light reminders with no navigation target. ``event_type``
    and ``details`` come straight off the event that caused the row, so the
    reader words each kind itself -- the same pair the timeline renders from.
    ``job_title``/``applicant_name``/``actor_name`` are resolved display
    strings, "" (or None for actor_name) when the referenced row is missing --
    same fallback convention as MyEvaluationDto/CommentDto. A null
    ``actor_name`` means nobody did it: the rules did.

    ``job_kind`` is the resolved posting's kind (None when the posting is
    missing), so consumers outside React can honour the display-only rule
    that an activity posting's `hired` stage reads as "Admitted".
    """

    id: int
    event_type: str
    details: dict = {}
    job_title: str = ""
    job_kind: JobKind | None = None
    applicant_name: str = ""
    actor_name: str | None = None
    created_at: datetime


class NotificationListDto(BaseDto):
    """A page of one user's notifications plus their total pending count."""

    notifications: list[NotificationDto]
    unread_count: int


class UnreadCountDto(BaseDto):
    """Returned by dismiss/dismiss-all so the frontend can update the badge without a refetch."""

    unread_count: int
