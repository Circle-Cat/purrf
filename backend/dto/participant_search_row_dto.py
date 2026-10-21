from backend.dto.base_internal_dto import BaseInternalDTO
from backend.common.mentorship_enums import (
    ApprovalStatus,
    PairStatus,
    ParticipantRole,
)


class ParticipantSearchPairRow(BaseInternalDTO):
    pair_id: int
    mentor_id: int
    mentee_id: int
    pair_status: PairStatus
    completed_count: int


class PersonSearchRow(BaseInternalDTO):
    """Who a row in an admin people search is, read off the users table."""

    user_id: int
    is_blocked: bool
    is_deactivated: bool
    is_internal: bool


class ParticipantSearchRow(PersonSearchRow):
    round_id: int | None
    participant_role: ParticipantRole | None
    approval_status: ApprovalStatus | None
    pairs: list[ParticipantSearchPairRow] = []
