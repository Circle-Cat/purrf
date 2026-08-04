from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class JobActivityEntity(Base):
    """One append-only entry in a job posting's audit timeline.

    Written by ``JobService`` inside the same transaction as the action it
    logs — never updated or deleted once written. ``event_type`` is one of
    the fixed strings ``"job_created"``, ``"review_opened"``,
    ``"review_decided"``. Mirrors ``ApplicationActivityEntity``.
    """

    __tablename__ = "job_activity"

    activity_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job.job_id", ondelete="CASCADE"), index=True, nullable=False
    )
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
