from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.mentorship_enums import ScormVersion, TrainingCategory


class TrainingCourseEntity(Base):
    """A course somebody can be assigned to and learn.

    Courses come in two shapes and the table has to hold both. The four that
    exist today are seed rows carrying a ``category`` and nothing else: their
    content lives outside purrf behind an environment-variable link, and they
    stay that way until somebody uploads a package for them. Courses created
    from here on have a package and no ``category`` -- adding a course stops
    being a code change.

    ``category`` is nullable and unique because of that split: it is the join
    back to the four hard-coded enum values that ``training.category`` and the
    mentorship matching gate still read, not a classification every course
    needs.

    A course with no ``verified_completable_at`` cannot be assigned to anybody.
    That is enforced in the service, not by a constraint, because the check is
    about what an admin may do rather than about what rows may exist.
    """

    __tablename__ = "training_course"

    course_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String, nullable=False)

    description: Mapped[str | None] = mapped_column(String)

    # Unique so the four seed rows stay one-to-one with the enum; nullable so
    # new courses do not have to invent a category to exist.
    category: Mapped[TrainingCategory | None] = mapped_column(
        Enum(
            TrainingCategory,
            name="training_category",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        unique=True,
    )

    # Deactivating stops new assignments. It never touches the people already
    # assigned, who keep their access and their progress -- which is why
    # nothing in this design deletes a course.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # GCS object prefix, e.g. "training/7/<uuid>/". NULL means no package has
    # ever been uploaded and the course still points at its external link.
    storage_prefix: Mapped[str | None] = mapped_column(String)

    # Entry page relative to the prefix, read from the manifest.
    entry_path: Mapped[str | None] = mapped_column(String)

    scorm_version: Mapped[ScormVersion | None] = mapped_column(
        Enum(
            ScormVersion,
            name="scorm_version",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )

    # The package's own coursePackageVersion. Overwriting compares against this
    # to decide whether learners' resume data can survive the new upload.
    package_version: Mapped[str | None] = mapped_column(String)

    # The package's own `reporting` setting, e.g. "passed-incomplete". Which
    # lesson_status counts as finished is per-course and must never be
    # hard-coded: the two real packages we hold disagree with each other.
    reporting_mode: Mapped[str | None] = mapped_column(String)

    package_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # Stamped the moment a trial run reports a status that maps to DONE. NULL
    # means unassignable. Cleared on every re-upload: a new export is a new
    # thing and the old proof does not carry over.
    verified_completable_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    verified_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )

    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
