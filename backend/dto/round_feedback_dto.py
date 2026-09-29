from pydantic import Field
from backend.dto.base_dto import BaseDto
from backend.common.mentorship_enums import ParticipantRole


class AdminPartnerFeedbackDto(BaseDto):
    """What one participant wrote about one of their partners."""

    partner_id: int
    # None when the partner's user row no longer resolves.
    partner_name: str | None = None
    rating: int | None = None
    feedback: str | None = None


class ParticipantFeedbackDto(BaseDto):
    user_id: int
    name: str
    role: ParticipantRole | None = None
    has_submitted: bool
    most_valuable_aspects: str | None = None
    challenges: str | None = None
    program_rating: int | None = None
    partner_feedback: list[AdminPartnerFeedbackDto] = Field(default_factory=list)


class RoundFeedbackDto(BaseDto):
    """A round's feedback as the admin console reads it: everyone it is asked
    of, sent or not."""

    round_id: int
    round_name: str
    owed: int
    sent: int
    participants: list[ParticipantFeedbackDto] = Field(default_factory=list)
