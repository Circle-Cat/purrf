from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum, DateTime, ForeignKey, func
from backend.common.mentorship_enums import TrainingStatus, TrainingCategory
from backend.common.base import Base


class TrainingEntity(Base):
    __tablename__ = "training"

    training_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )

    # Nullable since courses stopped being an enum. Rows for seed courses keep
    # their category, so registration and the matching gate -- which filter on
    # this column -- read as they always did. Courses created from the admin
    # page have none, and are correctly invisible to those two paths.
    category: Mapped[TrainingCategory | None] = mapped_column(
        Enum(
            TrainingCategory,
            name="training_category",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )

    completed_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    status: Mapped[TrainingStatus] = mapped_column(
        Enum(
            TrainingStatus,
            name="training_status",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )

    # Null until the user first registers for a round. The row is created at
    # admission so the task is visible immediately; RegistrationService stamps
    # the deadline on first registration and never overwrites it.
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    link: Mapped[str | None] = mapped_column(String)

    # Nullable only because the migration that adds it backfills from
    # `category`; every row written from here on carries one.
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_course.course_id", ondelete="RESTRICT"), index=True
    )

    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
