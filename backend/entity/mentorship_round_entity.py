from datetime import datetime
from sqlalchemy import Float, Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base


class MentorshipRoundEntity(Base):
    __tablename__ = "mentorship_round"

    round_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String)
    mentee_average_score: Mapped[float | None] = mapped_column(Float)
    mentor_average_score: Mapped[float | None] = mapped_column(Float)
    expectations: Mapped[str | None] = mapped_column(String)
    # Superseded by the timeline columns below and no longer read or written
    # by the app; only backend/backfill/ still reads it.
    description: Mapped[dict | None] = mapped_column(JSONB)
    required_meetings: Mapped[int] = mapped_column(Integer, default=5)
    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    promotion_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mentor_application_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    mentee_application_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    onboarding_notification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    # Registration closes here, for mentors and mentees alike, and onboarding
    # training is due by it. The application deadlines belong to recruiting.
    onboarding_deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    match_notification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    first_meeting_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    meeting_log_reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    meetings_completion_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    feedback_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    feedback_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
