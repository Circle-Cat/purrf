from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base


class ApplicationDraftEntity(Base):
    """A candidate's unsubmitted application form for one posting.

    Kept apart from ``application`` on purpose: every application row has been
    handed to the organisation and staff may read it, while a draft is private
    to the candidate until they submit it. Submitting deletes the draft.
    """

    __tablename__ = "application_draft"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_application_draft_user_job"),
    )

    application_draft_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job.job_id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Form state, in the submission snapshot's keys:
    # {"personal": {...}, "education": [...], "experience": [...],
    #  "answers": {...}, "resumeSha256": str | None,
    #  "resumeObjectKey": str | None}
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
