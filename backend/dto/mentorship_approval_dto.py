"""Request and response shapes of the mentorship approval endpoints."""

from datetime import datetime
from typing import Literal

from backend.common.approval_enums import ApprovalRequestStatus
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto


class ApprovalRequestCreateDto(BaseRequestDto):
    """Body of a request to approve something: who should decide, and why."""

    reviewer_id: int
    reason: str


class ParticipantMarkRequestDto(ApprovalRequestCreateDto):
    """Body of a request to mark a person in a round: which mark, and the
    pair it is about when there is one."""

    tag: Literal["no_show", "red_flag"]
    pair_id: int | None = None


class ApprovalReassignDto(BaseRequestDto):
    """Body of handing a pending request to another reviewer."""

    reviewer_id: int


class ApprovalDecisionDto(BaseRequestDto):
    """Body of a reviewer's decision. A rejection needs a comment."""

    decision: Literal["approve", "reject"]
    comment: str | None = None


class ApprovalPersonDto(BaseDto):
    user_id: int
    name: str | None = None


class ApprovalRoundDto(BaseDto):
    round_id: int
    name: str | None = None


class MentorshipApprovalDto(BaseDto):
    """One mentorship approval request as the console shows it."""

    request_id: int
    action: str
    status: ApprovalRequestStatus
    round: ApprovalRoundDto
    target_id: str
    # Who the request is about, for an exemption.
    person: ApprovalPersonDto | None = None
    raised_by: ApprovalPersonDto
    reviewer: ApprovalPersonDto
    reason: str | None = None
    decision_comment: str | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None
