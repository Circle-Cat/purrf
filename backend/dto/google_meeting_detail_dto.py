from backend.dto.base_internal_dto import BaseInternalDTO


class GoogleMeetingDetailDto(BaseInternalDTO):
    meeting_id: str
    meet_link: str
    start_datetime: str
    end_datetime: str
    created_datetime: str
    is_completed: bool
    entry_points: list[dict]
    conference_id: str | None = None
    has_unknown_absent: bool | None = None
    absent_user_id: int | None = None
    late_user_id: list[int] | None = None
    has_unknown_late: bool | None = None
    has_insufficient_duration: bool | None = None
