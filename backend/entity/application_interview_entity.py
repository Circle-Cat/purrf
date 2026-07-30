from datetime import datetime
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.recruiting_enums import ApplicationStage


class ApplicationInterviewEntity(Base):
    """The scheduled interview meeting for one application's stage+round.

    One row per (application_id, stage, round) — the same uniqueness
    `application_assignment` uses, because an interview belongs to exactly one
    assignee's round. Rescheduling updates the row in place (the Calendar
    event is patched, keeping its Meet link); cancelling **deletes** it, with
    the history left to `application_activity` — the same tombstone-free
    approach reject/blacklist take.

    Attendees are not stored: the candidate is `application.user_id`, the
    interviewer is the round's `application_assignment.assignee_id`, and the
    recruiter is `scheduled_by`. A stored snapshot could only drift from those.

    No timezone column either, deliberately. `start_at`/`end_at` are the
    authoritative instants, and every surface renders them in the VIEWER's own
    profile zone (falling back to their browser zone) — showing a recruiter's
    booking zone to someone in another country helps nobody. A stored
    booker-chosen zone would therefore be a column nothing is allowed to
    render. The wall clock the booker actually typed is kept in
    `application_activity` for audit, and Google Calendar holds the
    authoritative event with its own `timeZone`, which is what protects a
    future meeting if a jurisdiction changes its DST rules.
    """

    __tablename__ = "application_interview"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "stage",
            "round",
            name="uq_application_interview_app_stage_round",
        ),
    )

    interview_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.application_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(
            ApplicationStage,
            name="application_stage_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    round: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    google_event_id: Mapped[str] = mapped_column(String, nullable=False)
    # Google does not always return a hangoutLink (conference creation is
    # asynchronous on its side), so this stays nullable rather than blocking
    # a meeting that was otherwise created successfully.
    meet_link: Mapped[str | None] = mapped_column(String)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # The recruiter who first booked this meeting, and therefore the recruiter
    # on the invite. Never changed by an edit — otherwise every reschedule by
    # a different owner would add another attendee.
    scheduled_by: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
