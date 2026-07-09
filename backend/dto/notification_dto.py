from datetime import datetime

from backend.common.recruiting_enums import NotificationType
from backend.dto.base_dto import BaseDto


class NotificationDto(BaseDto):
    """One row in a user's notification list.

    application_id/round/comment_id are set for ASSIGNED_TO_EVALUATE and
    MENTIONED; job_id (only, no job_review_id) is exposed for the
    JOB_REVIEW_* types since the frontend only needs it to build a link.
    job_title/applicant_name/actor_name are resolved display strings,
    "" (or None for actor_name) when the referenced row is missing --
    same fallback convention as MyEvaluationDto/CommentDto.
    """

    id: int
    type: NotificationType
    application_id: int | None = None
    job_id: int | None = None
    round: int | None = None
    job_title: str = ""
    applicant_name: str = ""
    actor_name: str | None = None
    read: bool
    created_at: datetime


class NotificationListDto(BaseDto):
    """A page of one user's notifications plus their total unread count."""

    notifications: list[NotificationDto]
    unread_count: int


class UnreadCountDto(BaseDto):
    """Returned by mark-read/mark-all-read so the frontend can update the badge without a refetch."""

    unread_count: int
