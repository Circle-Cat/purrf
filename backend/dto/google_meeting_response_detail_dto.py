from backend.dto.base_dto import BaseDto


class GoogleMeetingResponseDetailDto(BaseDto):
    meeting_id: str
    meet_link: str
    attendees: list[int]
    start_datetime: str
    end_datetime: str
    is_completed: bool
    entry_points: list[dict]
