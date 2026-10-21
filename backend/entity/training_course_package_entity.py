from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.mentorship_enums import ScormVersion, TrainingPackageState


class TrainingCoursePackageEntity(Base):
    """One uploaded package, and which slot of its course it fills.

    The verification stamp lives here rather than on the course. A stamp is a
    statement about a package -- somebody ran this export to completion -- and
    holding it on the course meant every upload had to remember to clear it.

    The two partial unique indexes are what make "a course serves one package"
    true. They are constraints rather than service discipline because a second
    live row makes the question unanswerable rather than merely wrong.
    """

    __tablename__ = "training_course_package"
    __table_args__ = (
        Index(
            "ux_course_package_live",
            "course_id",
            unique=True,
            postgresql_where=text("state = 'live'"),
        ),
        Index(
            "ux_course_package_pending",
            "course_id",
            unique=True,
            postgresql_where=text("state = 'pending'"),
        ),
    )

    package_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    course_id: Mapped[int] = mapped_column(
        ForeignKey("training_course.course_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    state: Mapped[TrainingPackageState] = mapped_column(
        Enum(
            TrainingPackageState,
            name="training_package_state",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )

    # GCS object prefix, e.g. "training/7/<uuid>/".
    storage_prefix: Mapped[str] = mapped_column(String, nullable=False)

    # Entry page relative to the prefix, read from the manifest.
    entry_path: Mapped[str] = mapped_column(String, nullable=False)

    scorm_version: Mapped[ScormVersion] = mapped_column(
        Enum(
            ScormVersion,
            name="scorm_version",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )

    # The package's own coursePackageVersion. Absent from every export that
    # was not built by Rustici's toolchain.
    package_version: Mapped[str | None] = mapped_column(String)

    # The package's own `reporting` setting, e.g. "passed-incomplete". Which
    # lesson_status counts as finished is per-package and must not be
    # hard-coded: the two real packages we hold disagree with each other.
    reporting_mode: Mapped[str | None] = mapped_column(String)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )

    # NULL means nobody has run this package to completion.
    verified_completable_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    verified_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
