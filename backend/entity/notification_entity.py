from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.recruiting_enums import NotificationStatus


class NotificationEntity(Base):
    """One in-app notification for a single recipient.

    A row says only that this user needs to know about this event. What
    happened, who did it and what it was about live on the event it points
    at, so the same row serves the bell and the email without either
    carrying a copy of the story.

    ``status`` and ``claimed_at`` are the claim a sender takes before
    sending, so a redelivered message cannot send a second copy; a claim
    older than the ack deadline may be retaken, since a process that died
    mid-send would otherwise strand the row. ``dismissed_at`` marks a row as
    gone from the bell rather than deleting it, because that delivery state
    lives here too.
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("event.event_id", ondelete="CASCADE"), index=True, nullable=False
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
