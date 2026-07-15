from datetime import datetime
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.recruiting_enums import ApplicationStage


class ApplicationEntity(Base):
    """One candidate's application attempt to a posting.

    At most one NON-REJECTED row may exist per (job, user) — enforced by the
    partial unique index below. REJECTED attempts accumulate as immutable
    history; a re-apply creates a fresh row (see ApplicationService.submit).
    """

    __tablename__ = "application"
    __table_args__ = (
        Index(
            "uq_application_job_user_active",
            "job_id",
            "user_id",
            unique=True,
            postgresql_where=text("stage != 'rejected'"),
        ),
    )

    application_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job.job_id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(
            ApplicationStage,
            name="application_stage_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ApplicationStage.APPLIED,
        server_default=ApplicationStage.APPLIED.value,
        nullable=False,
    )
    # Card sub-status within a stage; reserved here, exercised by sub-project #2.
    sub_status: Mapped[str | None] = mapped_column(String)
    # Which round of the current stage the applicant is on (1-indexed).
    # Resets to 1 on every stage change; advanced only via an explicit owner
    # action (BoardService.set_round). Meaningless (always 1) for a stage
    # configured with a single round.
    current_round: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # Advisory flags (e.g. {"cold_freeze": {"thaw_date": "2026-04-01"}}).
    tags: Mapped[dict | None] = mapped_column(JSONB)
    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
