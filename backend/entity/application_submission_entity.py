from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base


class ApplicationSubmissionEntity(Base):
    """The answers a candidate submitted for an application.

    Written once, as version 1, when the candidate submits, and never changed
    afterwards. Re-applying after a rejection creates a new application with
    its own version 1.
    """

    __tablename__ = "application_submission"
    __mapper_args__ = {"exclude_properties": ["is_frozen"]}

    submission_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.application_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Unused, and dropped in the release after this one. It stays on the table
    # but is excluded from the mapper (__mapper_args__), so the ORM neither reads nor
    # writes it and pods on this code keep working after the column is gone.
    is_frozen = Column(Boolean, nullable=True)
    # Snapshot: {"personal": {...}, "education": [...], "experience": [...],
    #            "answers": {...}, "formSchema": {...}}
    # formSchema is the job's form as it stood when these answers were written,
    # so a reviewer reads them against the questions that were actually asked.
    submission: Mapped[dict | None] = mapped_column(JSONB)
    resume_object_key: Mapped[str | None] = mapped_column(String)
    resume_sha256: Mapped[str | None] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
