from datetime import datetime
from backend.dto.base_request_dto import BaseRequestDto


class TimelineCreateDto(BaseRequestDto):
    promotion_start_at: datetime
    mentor_application_deadline_at: datetime
    mentee_application_deadline_at: datetime
    onboarding_notification_at: datetime | None = None
    onboarding_deadline_at: datetime
    match_notification_at: datetime
    first_meeting_deadline_at: datetime | None = None
    meeting_log_reminder_at: datetime | None = None
    meetings_completion_deadline_at: datetime
    feedback_start_at: datetime | None = None
    feedback_deadline_at: datetime | None = None


class RoundsCreateDto(BaseRequestDto):
    id: int | None = None
    name: str
    expectations: str | None = None
    timeline: TimelineCreateDto
    required_meetings: int
