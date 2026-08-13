from pydantic import Field
from backend.dto.base_dto import BaseDto
from backend.common.mentorship_enums import ParticipantRole


class PartnerFeedbackDto(BaseDto):
    partner_id: int
    rating: int | None = None
    feedback: str | None = None


class FeedbackDto(BaseDto):
    participant_role: ParticipantRole
    has_submitted: bool
    sessions_completed: int | None = None
    most_valuable_aspects: str | None = None
    challenges: str | None = None
    program_rating: int | None = None
    partner_feedback: list[PartnerFeedbackDto] = Field(default_factory=list)
