from datetime import datetime
from sqlalchemy import Integer, Boolean, Enum, ForeignKey, DateTime, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.recruiting_enums import ApplicationStage


class ApplicationEntity(Base):
    """A candidate's application to a posting, stamped to a mentorship round."""

    __tablename__ = "application"

    application_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("mentorship_round.round_id"))
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(
            ApplicationStage,
            name="application_stage_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    form_answers: Mapped[dict | None] = mapped_column(JSONB)
    snapshot: Mapped[dict | None] = mapped_column(JSONB)
    is_viewed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    previous_application_id: Mapped[int | None] = mapped_column(
        ForeignKey("application.application_id")
    )
    rejected_round_id: Mapped[int | None] = mapped_column(
        ForeignKey("mentorship_round.round_id")
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "uq_application_active_user_job",
            "user_id",
            "job_id",
            unique=True,
            postgresql_where=text("stage NOT IN ('hired', 'rejected')"),
        ),
    )
