from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator

from backend.dto.base_request_dto import BaseRequestDto

ALLOWED_DURATION_MINUTES = {30, 45, 60, 90}


class MeetingBatchCreateDto(BaseRequestDto):
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
