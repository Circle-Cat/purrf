from datetime import datetime
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.recruiting_enums import ApplicationStage


class ApplicationEntity(Base):
    """One candidate's application to a posting (unique per job+user)."""

    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint("job_id", "user_id", name="uq_application_job_user"),
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
    # Advisory flags (e.g. {"cold_freeze": {"thaw_date": "2026-04-01"}}).
    tags: Mapped[dict | None] = mapped_column(JSONB)
    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
