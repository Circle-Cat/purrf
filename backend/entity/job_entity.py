from datetime import datetime
from sqlalchemy import Boolean, String, Integer, Enum, DateTime, func, text
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
    pipeline_config: Mapped[dict | None] = mapped_column(JSONB)
    pending_payload: Mapped[dict | None] = mapped_column(JSONB)
    screen_rules: Mapped[dict | None] = mapped_column(JSONB)
    profile_config: Mapped[dict | None] = mapped_column(JSONB)
    # Cold-freeze window in days before a rejected applicant may reapply to
    # this posting. Applies uniformly to activity and employment postings;
    # unset behaves as 0 (reapply allowed immediately).
    cooldown_days: Mapped[int | None] = mapped_column(Integer)
    was_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
