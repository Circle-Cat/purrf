from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.mentorship_enums import TrainingCategory


class TrainingCourseEntity(Base):
    """A course somebody can be assigned to and learn.

    The four seed rows carry a ``category`` and no package: their content lives
    outside purrf behind an environment-variable link. Courses created after
    this feature have a package and no category.

    A course with no live package cannot be assigned. That is enforced in the
    service rather than by a constraint: it governs what an admin may do, not
    what rows may exist.
    """

    __tablename__ = "training_course"

    course_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String, nullable=False)

    description: Mapped[str | None] = mapped_column(String)

    # Unique so the seed rows stay one-to-one with the enum; nullable so a new
    # course does not have to invent a category to exist.
    category: Mapped[TrainingCategory | None] = mapped_column(
        Enum(
            TrainingCategory,
            name="training_category",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        unique=True,
    )

    # Stops new assignments. People already assigned keep their access and
    # their progress; nothing deletes a course.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
