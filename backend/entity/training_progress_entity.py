from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class TrainingProgressEntity(Base):
    """The SCORM runtime state behind one assignment.

    One row per ``training`` row, created the first time a learner opens a
    course. It is a separate table rather than more columns on ``training``
    because ``training`` is read by the profile page, by registration and by
    the matching gate, none of which care what slide somebody is on -- and
    because the old link-only rows would carry these columns as permanent
    NULLs.

    ``lesson_status`` holds the SCORM value verbatim (``not attempted`` /
    ``incomplete`` / ``completed`` / ``passed`` / ``failed`` / ``browsed``).
    Mapping it to a ``TrainingStatus`` is a decision made when it is written,
    not a shape imposed on storage.
    """

    __tablename__ = "training_progress"

    progress_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    training_id: Mapped[int] = mapped_column(
        ForeignKey("training.training_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    lesson_status: Mapped[str | None] = mapped_column(String)

    # The course's own bookmark. Wiped, with suspend_data, when a new package
    # replaces the one a learner started on.
    lesson_location: Mapped[str | None] = mapped_column(String)

    # 🔴 Text with no length limit, and no length validation anywhere above it.
    #
    # The SCORM 1.2 spec caps this at 4096 characters, but real packages ship
    # driverOptions.js with USE_STRICT_SUSPEND_DATA_LIMITS = false and write
    # straight past it. A rejected write is invisible to the course: it carries
    # on, and the learner silently loses their place on the next visit. So the
    # only safe behaviour is to store whatever arrives.
    suspend_data: Mapped[str | None] = mapped_column(Text)

    score_raw: Mapped[Decimal | None] = mapped_column(Numeric(precision=8, scale=2))
    score_min: Mapped[Decimal | None] = mapped_column(Numeric(precision=8, scale=2))
    score_max: Mapped[Decimal | None] = mapped_column(Numeric(precision=8, scale=2))

    # Accumulated across sessions, in seconds. Courses report each session's
    # time separately and expect the total back.
    session_time_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
