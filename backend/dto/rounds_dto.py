from datetime import datetime
from backend.dto.base_dto import BaseDto


class TimelineDto(BaseDto):
    promotion_start_at: datetime | None = None
    application_deadline_at: datetime | None = None
    review_start_at: datetime | None = None
    acceptance_notification_at: datetime | None = None
    matching_completed_at: datetime | None = None
    match_notification_at: datetime | None = None
    first_meeting_deadline_at: datetime | None = None
    meetings_completion_deadline_at: datetime | None = None
    feedback_deadline_at: datetime | None = None


class RoundsDto(BaseDto):
    id: int
    name: str
    mentee_average_score: float | None = None
    mentor_average_score: float | None = None
    expectations: str | None = None
    required_meetings: int
    timeline: TimelineDto | None = None
