from backend.dto.base_dto import BaseDto
from backend.dto.partner_dto import PartnerDto
from backend.common.mentorship_enums import (
    ApprovalStatus,
    ParticipantRole,
    TrainingStatus,
)


class ParticipantRowDto(BaseDto):
    user_id: int
    round_id: int | None
    round_name: str | None
    pair_id: int | None
    first_name: str | None
    last_name: str | None
    preferred_name: str | None
    primary_email: str | None
    alternative_emails: list[str]
    matched_user: PartnerDto | None
    participant_role: ParticipantRole | None
    approval_status: ApprovalStatus | None
    mentor_onboarding_status: TrainingStatus | None
    mentee_onboarding_status: TrainingStatus | None
    completed_meeting_count: int | None
    required_meetings: int | None


class ParticipantSearchDto(BaseDto):
    participant_rows: list[ParticipantRowDto]
    total: int
