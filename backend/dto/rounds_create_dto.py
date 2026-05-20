from datetime import datetime
from backend.dto.base_request_dto import BaseRequestDto


class TimelineCreateDto(BaseRequestDto):
    promotion_start_at: datetime
    mentor_application_deadline_at: datetime
    mentee_application_deadline_at: datetime
    training_notification_at: datetime | None = None
    training_deadline_at: datetime | None = None
    match_notification_at: datetime
    matching_completed_at: datetime | None = None
    meeting_log_reminder_at: datetime | None = None
    meetings_completion_deadline_at: datetime
    feedback_start_at: datetime | None = None
    feedback_deadline_at: datetime | None = None
    review_start_at: datetime | None = None
    acceptance_notification_at: datetime | None = None
    first_meeting_deadline_at: datetime | None = None


class RoundsCreateDto(BaseRequestDto):
    id: int | None = None
    name: str
    mentee_average_score: float | None = None
    mentor_average_score: float | None = None
    expectations: str | None = None
    timeline: TimelineCreateDto
    required_meetings: int
