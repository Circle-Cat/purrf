from typing import Literal
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.mentorship_enums import ApprovalStatus, ParticipantRole


class ParticipantSearchFilterDto(BaseRequestDto):
    user_id: int | None = None
    name: str | None = None
    email: str | None = None
    matched_user: str | None = None
    round_id: int | None = None
    participant_role: ParticipantRole | None = None
    approval_status: ApprovalStatus | None = None
    onboarding_status: Literal["completed", "incomplete"] | None = None
    participation_status: Literal["participant", "non_participant"] | None = None
