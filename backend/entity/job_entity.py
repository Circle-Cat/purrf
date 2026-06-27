from datetime import datetime
from sqlalchemy import String, Integer, Enum, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.recruiting_enums import JobKind, JobStatus
from backend.common.mentorship_enums import ParticipantRole


class JobEntity(Base):
    """A recruiting posting. MVP creates two ACTIVITY postings (mentor, mentee)."""

    __tablename__ = "job"

    job_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[JobKind] = mapped_column(
        Enum(
            JobKind,
            name="job_kind_enum",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )
    mentorship_role: Mapped[ParticipantRole | None] = mapped_column(
        Enum(
            ParticipantRole,
            name="job_mentorship_role_enum",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=JobStatus.DRAFT,
        server_default=JobStatus.DRAFT.value,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    form_schema: Mapped[dict | None] = mapped_column(JSONB)
    pipeline_config: Mapped[list | None] = mapped_column(JSONB)
    pending_form_schema: Mapped[dict | None] = mapped_column(JSONB)
    pending_pipeline_config: Mapped[list | None] = mapped_column(JSONB)
    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
