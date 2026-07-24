from backend.dto.base_internal_dto import BaseInternalDTO
from backend.common.mentorship_enums import ApprovalStatus, ParticipantRole


class ParticipantSearchRow(BaseInternalDTO):
    user_id: int
    round_id: int | None
    pair_id: int | None
    participant_role: ParticipantRole | None
    approval_status: ApprovalStatus | None
    completed_count: int | None
    mentor_id: int | None
    mentee_id: int | None
    meeting_log: dict | None = None
