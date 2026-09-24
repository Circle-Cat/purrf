from datetime import datetime
from backend.common.mentorship_enums import RoundStatus
from backend.dto.base_dto import BaseDto


class TimelineDto(BaseDto):
    promotion_start_at: datetime | None = None
    mentor_application_deadline_at: datetime | None = None
    mentee_application_deadline_at: datetime | None = None
    onboarding_notification_at: datetime | None = None
    onboarding_deadline_at: datetime
    match_notification_at: datetime | None = None
    first_meeting_deadline_at: datetime | None = None
    meeting_log_reminder_at: datetime | None = None
    meetings_completion_deadline_at: datetime | None = None
    feedback_start_at: datetime | None = None
    feedback_deadline_at: datetime | None = None


class RoundsDto(BaseDto):
    id: int
    name: str
    active_pairs: int | None = None
    matched_participants: int | None = None
    total_completed_meetings: int | None = None
    mentee_average_score: float | None = None
    mentor_average_score: float | None = None
    expectations: str | None = None
    required_meetings: int
    timeline: TimelineDto | None = None
    status: RoundStatus | None = None


class RoundSlotsDto(BaseDto):
    """Which rounds the Personal Dashboard acts on, as of the server's clock.

    ``registration_round_id`` is the round open for registration or, when
    none is, the most recently promoted one, kept viewable. The matching
    result always speaks about that same round.
    """

    registration_round_id: int | None = None
    registration_round_name: str | None = None
    registration_deadline_at: datetime | None = None
    is_registration_open: bool = False
    can_view_match: bool = False
    is_feedback_enabled: bool = False
    active_round_id: int | None = None
