from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.onboarding_guide_enums import GuideProgressStatus


class UserGuideProgressEntity(Base):
    """How far one user has got with one onboarding guide.

    One row per user and guide, written the first time the user finishes,
    dismisses or snoozes it; no row means the guide has never been seen.
    ``snooze_count`` counts every time the user closed the guide for now,
    which is what turns repeated snoozing into a dismissal.
    """

    __tablename__ = "user_guide_progress"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    guide_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[GuideProgressStatus] = mapped_column(
        Enum(
            GuideProgressStatus,
            name="guide_progress_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    snooze_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
