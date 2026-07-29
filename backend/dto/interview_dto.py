"""DTOs for the recruiting interview-meeting scheduling endpoints."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator

from backend.dto.base_dto import BaseDto

ALLOWED_DURATIONS = (30, 45, 60, 90)


class InterviewScheduleRequestDto(BaseDto):
    """A booking request in the recruiter's own wall-clock terms.

    ``timezone`` is an IANA name (e.g. ``America/Los_Angeles``) — the same
    form the shared frontend ``TimezoneSelector`` emits and ``users.timezone``
    stores.

    Wall-clock rather than a UTC instant because the zone itself has to be
    stored (the card renders "14:00 - 14:45 America/Los_Angeles" and the dialog
    re-selects the zone) — a frontend that converted to UTC would throw it
    away.
    """

    assignee_id: int
    date: date
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    duration_minutes: int
    timezone: str

    @field_validator("duration_minutes")
    @classmethod
    def _known_duration(cls, value):
        if value not in ALLOWED_DURATIONS:
            raise ValueError(f"duration_minutes must be one of {ALLOWED_DURATIONS}")
        return value

    @field_validator("timezone")
    @classmethod
    def _real_iana_zone(cls, value):
        # Validated as "a real IANA zone", not against a whitelist. The
        # frontend already offers a closed list (the shared TimezoneSelector,
        # backed by constants/Timezones.js); copying those 27 keys here would
        # create a second list guaranteed to drift from the first. What the
        # backend must reject is a bogus string, and ZoneInfo does exactly that.
        try:
            ZoneInfo(value)
        except Exception as e:
            raise ValueError(f"unknown IANA timezone: {value!r}") from e
        return value


class InterviewDto(BaseDto):
    """One scheduled interview meeting, as the detail page renders it."""

    interview_id: int
    stage: str
    round: int
    start_at: datetime
    end_at: datetime
    timezone: str
    meet_link: str | None = None
    assignee_id: int | None = None
    assignee_name: str | None = None
    scheduled_by_name: str | None = None
