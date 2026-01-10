from datetime import date
from backend.dto.base_dto import BaseDto


class TimelineDto(BaseDto):
    promotion_start_at: date | None = None
    application_deadline_at: date | None = None
    review_start_at: date | None = None
    acceptance_notification_at: date | None = None
    matching_completed_at: date | None = None
    match_notification_at: date | None = None
    first_meeting_deadline_at: date | None = None
    meetings_completion_deadline_at: date | None = None
    feedback_deadline_at: date | None = None


class RoundsDto(BaseDto):
    id: int
    name: str
    required_meetings: int
    timeline: TimelineDto | None = None
