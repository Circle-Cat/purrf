from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.recruiting_enums import NotificationStatus, NotificationType


class NotificationEntity(Base):
    """One in-app notification for a single recipient.

    A row is written in the same transaction as the change it announces, and
    is never rewritten except by the two marks below.

    Two shapes overlap here. The columns naming what the notification is
    about (``type`` and the ids beside it) describe it directly; ``event_id``
    points at an :class:`EventEntity` that describes it instead. Both are
    nullable because each path sets only its own, and ``type IS NULL`` is how
    a row of the second kind is recognised.

    ``status`` and ``claimed_at`` are the claim a sender takes before sending,
    so a redelivered message cannot send a second copy; a claim older than the
    ack deadline may be retaken, since a process that died mid-send would
    otherwise strand the row. ``dismissed_at`` marks a row as gone from the
    bell rather than deleting it, because that delivery state lives here too.
    """

    __tablename__ = "notification"
    __table_args__ = (
        Index("ix_notification_user_undismissed", "user_id", "dismissed_at"),
        Index("ix_notification_pending", "status", "created_at"),
    )

    notification_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[NotificationType | None] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("event.event_id", ondelete="CASCADE"), index=True, nullable=True
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(
            NotificationStatus,
            name="notification_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=NotificationStatus.PENDING,
        server_default=NotificationStatus.PENDING.value,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
