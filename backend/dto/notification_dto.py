from datetime import datetime

from backend.common.recruiting_enums import NotificationType
from backend.dto.base_dto import BaseDto


class NotificationDto(BaseDto):
    """One row in a user's notification list.

    Notifications are light reminders with no navigation target: dismissing
    one deletes it, so every listed row is pending/unread. application_id/
    round/comment_id are set for ASSIGNED_TO_EVALUATE and MENTIONED; job_id
    for the JOB_REVIEW_* types. job_title/applicant_name/actor_name are
    resolved display strings, "" (or None for actor_name) when the
    referenced row is missing -- same fallback convention as
    MyEvaluationDto/CommentDto.
    """

    id: int
    type: NotificationType
    application_id: int | None = None
    job_id: int | None = None
    round: int | None = None
    job_title: str = ""
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
