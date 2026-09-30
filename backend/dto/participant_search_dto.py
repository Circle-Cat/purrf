from backend.dto.base_dto import BaseDto
from backend.dto.partner_dto import PartnerDto
from backend.common.mentorship_enums import (
    ApprovalStatus,
    ParticipantRole,
    TrainingStatus,
)


class ParticipantPairDto(BaseDto):
    pair_id: int
    partner: PartnerDto
    completed_meeting_count: int


class ParticipantRowDto(BaseDto):
    user_id: int
    round_id: int | None
    round_name: str | None
    first_name: str | None
    last_name: str | None
    preferred_name: str | None
    primary_email: str | None
    alternative_emails: list[str]
    is_blocked: bool
    is_deactivated: bool
    is_internal: bool
    participant_role: ParticipantRole | None
    approval_status: ApprovalStatus | None
    mentor_onboarding_status: TrainingStatus | None
    mentee_onboarding_status: TrainingStatus | None
    pairs: list[ParticipantPairDto]
    required_meetings: int | None


class ParticipantSearchDto(BaseDto):
    participant_rows: list[ParticipantRowDto]
    total: int
