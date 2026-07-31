from datetime import datetime
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.mentorship_enums import MeetingSource

# The columns that only ever apply to a GOOGLE row. Named once so the CHECK
# constraint below and any future reader agree on the list.
_GOOGLE_ONLY_COLUMNS = (
    "meet_link",
    "google_meeting_code",
    "entry_points",
    "absent_user_id",
    "late_user_ids",
    "has_unknown_absent",
    "has_unknown_late",
    "has_insufficient_duration",
    "last_sync_at",
)


class MentorshipMeetingEntity(Base):
    """One mentorship meeting, of either generation.

    Replaces the two arrays that used to live under
    ``mentorship_pairs.meeting_log`` -- ``meeting_time_list`` (manual) and
    ``google_meetings`` (Purrf-created). Splitting them into rows is what makes
    a manual entry deletable, a mistyped field a startup error instead of a
    silently null read, and a pair holding both generations merely untidy
    rather than unrecoverable.

    ``completed_count`` on ``mentorship_pairs`` stays as a denormalized cache:
    it is summed per round in SQL and projected into participant search without
    loading meeting rows at all. It now has exactly one derivation.
    """

    __tablename__ = "mentorship_meeting"

    # For a MANUAL row this is a uuid4 Purrf generated. For a GOOGLE row it is
    # the Google Calendar event id -- kept as-is because
    # `batch_delete_google_meetings` passes this value straight to the
    # Calendar API. For a LEGACY row it is a synthesized `legacy-<pair_id>-<n>`
    # string, since there was never a real id to preserve. Three different
    # provenances behind one column, all preserved verbatim by the migration.
    meeting_id: Mapped[str] = mapped_column(String, primary_key=True)
    pair_id: Mapped[int] = mapped_column(
        ForeignKey("mentorship_pairs.pair_id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[MeetingSource] = mapped_column(
        Enum(
            MeetingSource,
            name="meeting_source_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    # Nullable ONLY for LEGACY rows -- see the CHECK constraint below. Those
    # historical rounds recorded a count and nothing else; a fabricated
    # timestamp would read as a real one everywhere it is displayed.
    start_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # --- GOOGLE only, guarded by the CHECK constraint below ---

    meet_link: Mapped[str | None] = mapped_column(String)
    # The Meet meeting code (`abc-defg-hij`), taken from the Calendar event's
    # conferenceData.conferenceId. NOT a Meet conference *record*
    # (`conferenceRecords/...`), which is per actual meeting and changes every
    # time; this is per space and stable. It is the only join key between a row
    # here and Google's attendance data.
    google_meeting_code: Mapped[str | None] = mapped_column(String)
    entry_points: Mapped[list | None] = mapped_column(JSONB)

    # --- attendance results, written only by the attendance sweep ---

    absent_user_id: Mapped[int | None] = mapped_column(Integer)
    # NULL means attendance was never evaluated; an empty array means it was
    # evaluated and nobody was late.
    late_user_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    has_unknown_absent: Mapped[bool | None] = mapped_column(Boolean)
    has_unknown_late: Mapped[bool | None] = mapped_column(Boolean)
    has_insufficient_duration: Mapped[bool | None] = mapped_column(Boolean)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Only a LEGACY row may lack times; everything else must have both,
        # ordered.
        CheckConstraint(
            "source = 'legacy' OR ("
            "start_datetime IS NOT NULL AND end_datetime IS NOT NULL "
            "AND end_datetime > start_datetime)",
            name="times",
        ),
        # This is what makes a wide table with a discriminator honest rather
        # than a flattened blob: the nine columns above are meaningless for a
        # manual or legacy entry, and the database now says so.
        CheckConstraint(
            "source = 'google' OR ("
            + " AND ".join(f"{c} IS NULL" for c in _GOOGLE_ONLY_COLUMNS)
            + ")",
            name="google_fields",
        ),
        Index("ix_mentorship_meeting_pair_start", "pair_id", "start_datetime"),
        Index(
            "ix_mentorship_meeting_google_code",
            "google_meeting_code",
            postgresql_where=text("google_meeting_code IS NOT NULL"),
        ),
        Index(
            "ix_mentorship_meeting_pending",
            "pair_id",
            postgresql_where=text("is_completed = false"),
        ),
    )
