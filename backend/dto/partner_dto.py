from backend.dto.base_dto import BaseDto
from backend.common.mentorship_enums import ParticipantRole


class PartnerDto(BaseDto):
    id: int
    first_name: str
    last_name: str
    preferred_name: str
    primary_email: str
    participant_role: ParticipantRole | None = None
    recommendation_reason: str | None = None
