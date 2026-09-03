from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class TrainingProgressEntity(Base):
    """The SCORM runtime state behind one assignment.

    Separate from ``training`` because the profile page, registration and the
    matching gate all read that table and none of them care what slide somebody
    is on -- and because link-only rows would carry these columns as permanent
    NULLs.

    ``lesson_status`` holds the SCORM value verbatim (``not attempted`` /
    ``incomplete`` / ``completed`` / ``passed`` / ``failed`` / ``browsed``).
    """

    __tablename__ = "training_progress"

    progress_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    training_id: Mapped[int] = mapped_column(
        ForeignKey("training.training_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    lesson_status: Mapped[str | None] = mapped_column(String)

    lesson_location: Mapped[str | None] = mapped_column(String)

    # Text with no length limit, and no length validation above it either.
    # Real packages disable the SCORM 1.2 4096-character cap and write past it.
    # A rejected write is invisible to the course: it carries on, and the
    # learner silently loses their place. Never add a length here.
    suspend_data: Mapped[str | None] = mapped_column(Text)

    score_raw: Mapped[Decimal | None] = mapped_column(Numeric(precision=8, scale=2))
    score_min: Mapped[Decimal | None] = mapped_column(Numeric(precision=8, scale=2))
    score_max: Mapped[Decimal | None] = mapped_column(Numeric(precision=8, scale=2))

    # Accumulated across sessions, in seconds.
    session_time_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
