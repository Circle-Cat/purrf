from pydantic import field_validator

from backend.dto.meeting_slot_request_dto import MeetingSlotRequestDto

ALLOWED_INTERVAL_WEEKS = {1, 2}
MIN_SESSION_COUNT = 1
MAX_SESSION_COUNT = 12


class MeetingBatchCreateDto(MeetingSlotRequestDto):
    interval_weeks: int = 1
    count: int = 1

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
