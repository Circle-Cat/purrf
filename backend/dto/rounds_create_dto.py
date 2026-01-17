from datetime import date
from backend.dto.base_request_dto import BaseRequestDto


class TimelineCreateDto(BaseRequestDto):
    promotion_start_at: date
    application_deadline_at: date
    review_start_at: date
    acceptance_notification_at: date
    matching_completed_at: date
    match_notification_at: date
    first_meeting_deadline_at: date
    meetings_completion_deadline_at: date
    feedback_deadline_at: date


class RoundsCreateDto(BaseRequestDto):
    id: int | None = None
    name: str
    mentee_average_score: float | None = None
    mentor_average_score: float | None = None
    expectations: str | None = None
    timeline: TimelineCreateDto
    required_meetings: int
