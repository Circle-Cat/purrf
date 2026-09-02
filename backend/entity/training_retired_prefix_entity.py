from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class TrainingRetiredPrefixEntity(Base):
    """A storage prefix a newer upload replaced, waiting to be deleted.

    Deletion is delayed rather than immediate because a resource request can be
    in flight across the switch, and tokens outlive it by up to 12 hours.
    Deleting at once turns those into 404s in the middle of somebody's course.
    """

    __tablename__ = "training_retired_prefix"

    retired_prefix_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    course_id: Mapped[int] = mapped_column(
        ForeignKey("training_course.course_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    storage_prefix: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # Not before this moment. Set to the retirement plus a margin comfortably
    # wider than a token's life.
    delete_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
