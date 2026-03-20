from datetime import datetime, timedelta

from pydantic import field_validator, model_validator

from backend.dto.base_request_dto import BaseRequestDto


class GoogleMeetingCreateDto(BaseRequestDto):
    partner_id: int
    round_id: int
    start_datetime: datetime
    end_datetime: datetime

    @field_validator("start_datetime", "end_datetime")
    def validate_utc_datetime(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() != timedelta(0):
            raise ValueError(f"Datetime must be UTC timezone-aware, got: {v}")
        return v

    @model_validator(mode="after")
    def validate_datetime_range(self):
        if self.start_datetime >= self.end_datetime:
            raise ValueError("start_datetime must be before end_datetime")
        return self
