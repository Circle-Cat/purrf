from backend.dto.base_dto import BaseDto


class GoogleMeetingDeleteResponseDto(BaseDto):
    succeeded_meeting_ids: list[str]
    failed_meeting_ids: list[str]
