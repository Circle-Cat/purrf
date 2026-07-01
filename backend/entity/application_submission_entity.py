from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base


class ApplicationSubmissionEntity(Base):
    """An append-only submission version for an application.

    While the application is Applied the current version is overwritten in
    place; freezing (sub-project #2) or re-applying after a rejection mints a
    new version, so prior versions survive for a later diff.
    """

    __tablename__ = "application_submission"

    submission_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.application_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Snapshot: {"personal": {...}, "education": [...], "experience": [...], "answers": {...}}
    submission: Mapped[dict | None] = mapped_column(JSONB)
    resume_object_key: Mapped[str | None] = mapped_column(String)
    resume_sha256: Mapped[str | None] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
