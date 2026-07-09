from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.recruiting_enums import NotificationType


class NotificationEntity(Base):
    """One in-app notification for a single recipient.

    Written synchronously, in the same transaction as the triggering
    event, by BoardService (assignment/mention), ApplicationService
    (default-assignee materialization), and JobService (review
    request/decision) -- never updated except to set read_at.

    Exactly one of application_id or (job_id, job_review_id) is set,
    never both: application_id/round/comment_id serve
    ASSIGNED_TO_EVALUATE and MENTIONED; job_id/job_review_id serve
    JOB_REVIEW_REQUESTED/JOB_REVIEW_APPROVED/JOB_REVIEW_REJECTED.
    """

    __tablename__ = "notification"

    notification_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("application.application_id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("application_comment.comment_id", ondelete="CASCADE"),
        nullable=True,
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("job.job_id", ondelete="CASCADE"), index=True, nullable=True
    )
    job_review_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_review.review_id", ondelete="CASCADE"), nullable=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
