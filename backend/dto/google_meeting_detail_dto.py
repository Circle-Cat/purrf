from backend.dto.base_internal_dto import BaseInternalDTO


class GoogleMeetingDetailDto(BaseInternalDTO):
    meeting_id: str
    meet_link: str
    start_datetime: str
    end_datetime: str
    is_completed: bool
    entry_points: list[dict]
    conference_id: str | None = None
