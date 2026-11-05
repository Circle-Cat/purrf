from typing import Literal
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.mentorship_email_enums import (
    MentorshipEmailNotificationState,
    MentorshipEmailStage,
)
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
    # Only the people eligible for matching in round_id; needs the round to
    # be in progress.
    eligible: bool | None = None
    # Only the people kept out of matching in round_id by their history
    # alone; needs the round to be in progress.
    needs_exemption: bool | None = None
    # Who this round's notification of one stage has or has not reached;
    # both or neither, and only within a round.
    notification_stage: MentorshipEmailStage | None = None
    notification_state: MentorshipEmailNotificationState | None = None


class UnregisteredFilterDto(BaseRequestDto):
    user_id: int | None = None
    q: str | None = None
    account_status: Literal["active", "blocked", "deactivated"] | None = None
    internal: Literal["internal", "external"] | None = None
    admitted_role: ParticipantRole | None = None
    # Who this round's notification of one stage has or has not reached;
    # both or neither, and only within a round.
    notification_stage: MentorshipEmailStage | None = None
    notification_state: MentorshipEmailNotificationState | None = None
