from datetime import datetime, timedelta
from backend.dto.base_request_dto import BaseRequestDto
from pydantic import field_validator, model_validator


class MeetingCreateDto(BaseRequestDto):
    round_id: int
    start_datetime: datetime
    end_datetime: datetime
    is_completed: bool

    @field_validator("start_datetime", "end_datetime")
    def validate_utc_datetime(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() != timedelta(0):
            raise ValueError(f"Datetime must be UTC timezone-aware, got: {v}")
        return v

    @model_validator(mode="after")
    def validate_time_order(self) -> "MeetingCreateDto":
        if self.start_datetime >= self.end_datetime:
            raise ValueError(
                f"End time ({self.end_datetime}) must be later than start time ({self.start_datetime})."
            )
        return self
