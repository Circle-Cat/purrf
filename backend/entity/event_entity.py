from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class EventEntity(Base):
    """One thing that happened, in any domain.

    Append-only. This is the single source of truth for "what happened":
    the timeline reads it by subject, and a notification points at the row
    for the event the recipient needs to know about.

    ``subject_type`` is a free-form string rather than an enum on purpose.
    Mentorship and leave management will both write here, and adding a
    domain must not require altering the table. ``event_type`` carries a
    domain prefix (``"recruiting.reassigned"``) so ownership is visible at
    a glance and two domains cannot collide on a bare ``"stage_changed"``.

    ``actor_id`` is NULL when the system did it under its own rules rather
    than on anyone's behalf -- a screen rule rejecting an application, or a
    stage's default assignee being materialised. Those are triggered by the
    candidate's own request, so naming them as the actor would tell staff
    the applicant rejected the applicant; the notification copy also picks
    its "happened automatically" wording off a null actor. Readers must
    keep null distinct from "there was an actor but their row is gone".
    """

    __tablename__ = "event"
    __table_args__ = (Index("ix_event_subject", "subject_type", "subject_id"),)

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
