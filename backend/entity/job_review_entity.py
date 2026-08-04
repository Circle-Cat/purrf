from datetime import datetime
from sqlalchemy import String, Integer, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.recruiting_enums import JobReviewStatus, JobReviewKind


class JobReviewEntity(Base):
    """One review cycle for a job posting (submit -> approve/reject)."""

    __tablename__ = "job_review"

    review_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), nullable=False)
    submitted_by: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    status: Mapped[JobReviewStatus] = mapped_column(
        Enum(
            JobReviewStatus,
            name="job_review_status_enum",
            values_callable=lambda o: [e.value for e in o],
        ),
        default=JobReviewStatus.PENDING,
        server_default=JobReviewStatus.PENDING.value,
        nullable=False,
    )
    kind: Mapped[JobReviewKind] = mapped_column(
        Enum(
            JobReviewKind,
            name="job_review_kind_enum",
            values_callable=lambda o: [e.value for e in o],
        ),
        nullable=False,
    )
    submit_message: Mapped[str | None] = mapped_column(String)
    reject_comment: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
