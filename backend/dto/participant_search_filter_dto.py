from typing import Literal
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.mentorship_enums import ApprovalStatus, ParticipantRole


class ParticipantSearchFilterDto(BaseRequestDto):
    user_id: int | None = None
    q: str | None = None
    account_status: Literal["active", "blocked", "deactivated"] | None = None
    internal: Literal["internal", "external"] | None = None
    round_id: int | None = None
    participant_role: ParticipantRole | None = None
    approval_status: ApprovalStatus | None = None
    onboarding_status: Literal["completed", "incomplete"] | None = None


class UnregisteredFilterDto(BaseRequestDto):
    user_id: int | None = None
    q: str | None = None
    account_status: Literal["active", "blocked", "deactivated"] | None = None
    internal: Literal["internal", "external"] | None = None
    admitted_role: ParticipantRole | None = None
