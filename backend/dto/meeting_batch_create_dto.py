from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator, model_validator

from backend.dto.base_request_dto import BaseRequestDto

ALLOWED_DURATION_MINUTES = {30, 45, 60, 90}
ALLOWED_INTERVAL_WEEKS = {1, 2}
MIN_SESSION_COUNT = 1
MAX_SESSION_COUNT = 12


class MeetingBatchCreateDto(BaseRequestDto):
    round_id: int
    partner_id: int
    timezone: str
    start_date: date
    start_time: str  # local wall-clock time, "HH:MM"
    duration_minutes: int
    interval_weeks: int = 1
    count: int = 1

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

    @field_validator("interval_weeks")
    def validate_interval_weeks(cls, v: int) -> int:
        if v not in ALLOWED_INTERVAL_WEEKS:
            raise ValueError(
                f"interval_weeks must be one of {sorted(ALLOWED_INTERVAL_WEEKS)}"
            )
        return v

    @field_validator("count")
    def validate_count(cls, v: int) -> int:
        if not (MIN_SESSION_COUNT <= v <= MAX_SESSION_COUNT):
            raise ValueError(
                f"count must be between {MIN_SESSION_COUNT} and {MAX_SESSION_COUNT}"
            )
        return v

    @model_validator(mode="after")
    def validate_start_not_in_past(self) -> "MeetingBatchCreateDto":
        start_dt = datetime.combine(
            self.start_date,
            datetime.strptime(self.start_time, "%H:%M").time(),
            tzinfo=ZoneInfo(self.timezone),
        )
        if start_dt < datetime.now(timezone.utc):
            raise ValueError("start time must be in the future")
        return self
