from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator, model_validator

from backend.dto.base_request_dto import BaseRequestDto
from backend.dto.meeting_batch_create_dto import ALLOWED_DURATION_MINUTES


class MeetingRescheduleDto(BaseRequestDto):
    """Move one already-booked meeting to a new slot.

    The same wall-clock contract as creation -- a local date, an HH:MM local
    time and the zone they are meant in -- because the server, not the
    browser, owns the conversion to UTC.

    No `interval_weeks` / `count`: a reschedule moves exactly one meeting.
    Moving a whole series is a separate feature.
    """

    round_id: int
    partner_id: int
    timezone: str
    start_date: date
    start_time: str  # local wall-clock time, "HH:MM"
    duration_minutes: int

    @field_validator("timezone")
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, KeyError):
            raise ValueError(f"Invalid timezone: {v}")
        return v

    @field_validator("start_time")
    def validate_start_time(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError(f"start_time must be in HH:MM format, got: {v}")
        return v

    @field_validator("duration_minutes")
    def validate_duration_minutes(cls, v: int) -> int:
        if v not in ALLOWED_DURATION_MINUTES:
            raise ValueError(
                f"duration_minutes must be one of {sorted(ALLOWED_DURATION_MINUTES)}"
            )
        return v

    @model_validator(mode="after")
    def validate_start_not_in_past(self) -> "MeetingRescheduleDto":
        start_dt = datetime.combine(
            self.start_date,
            datetime.strptime(self.start_time, "%H:%M").time(),
            tzinfo=ZoneInfo(self.timezone),
        )
        if start_dt < datetime.now(timezone.utc):
            raise ValueError("start time must be in the future")
        return self
