from backend.dto.base_dto import BaseDto
from backend.dto.google_meeting_response_detail_dto import (
    GoogleMeetingResponseDetailDto,
)


class GoogleMeetingCreateFailureDto(BaseDto):
    index: int
    start_datetime: str
    reason: str


class GoogleMeetingBatchCreateResponseDto(BaseDto):
    created: list[GoogleMeetingResponseDetailDto]
    failed: list[GoogleMeetingCreateFailureDto]
