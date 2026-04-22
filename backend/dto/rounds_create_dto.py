from datetime import datetime
from backend.dto.base_request_dto import BaseRequestDto


class TimelineCreateDto(BaseRequestDto):
    promotion_start_at: datetime
    application_deadline_at: datetime
    review_start_at: datetime
    acceptance_notification_at: datetime
    matching_completed_at: datetime
    match_notification_at: datetime
    first_meeting_deadline_at: datetime
    meetings_completion_deadline_at: datetime
    feedback_deadline_at: datetime


class RoundsCreateDto(BaseRequestDto):
    id: int | None = None
    name: str
    mentee_average_score: float | None = None
    mentor_average_score: float | None = None
    expectations: str | None = None
    timeline: TimelineCreateDto
    required_meetings: int
