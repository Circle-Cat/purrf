from backend.dto.base_dto import BaseDto
from backend.dto.mentorship_approval_dto import MentorshipApprovalDto
from backend.dto.partner_dto import PartnerDto
from datetime import datetime
from backend.common.mentorship_enums import (
    ApprovalStatus,
    MeetingNoteTag,
    ParticipantRole,
    TrainingStatus,
)


class AttendanceIssueDto(BaseDto):
    start_datetime: datetime
    note: list[MeetingNoteTag]


class ParticipantPairDto(BaseDto):
    pair_id: int
    partner: PartnerDto
    completed_meeting_count: int
    attendance_issues: list[AttendanceIssueDto]


class PersonRowDto(BaseDto):
    """The person columns every admin people search row shows."""

    user_id: int
    first_name: str | None
    last_name: str | None
    preferred_name: str | None
    primary_email: str | None
    alternative_emails: list[str]
    is_blocked: bool
    is_deactivated: bool
    is_internal: bool


class ExemptionFindingDto(BaseDto):
    """One history problem that keeps someone out of matching. ``reason`` is
    quit_after_match or meetings_short; a shortfall carries the meetings held
    and required."""

    reason: str
    round_id: int | None = None
    round_name: str | None = None
    completed: int | None = None
    required: int | None = None


class ParticipantRowDto(PersonRowDto):
    round_id: int | None
    round_name: str | None
    participant_role: ParticipantRole | None
    approval_status: ApprovalStatus | None
    mentor_onboarding_status: TrainingStatus | None
    mentee_onboarding_status: TrainingStatus | None
    pairs: list[ParticipantPairDto]
    required_meetings: int | None
    # Set only in the Needs exemption list: why the person needs one, and
    # the request for it waiting on a reviewer, if there is one.
    exemption_findings: list[ExemptionFindingDto] = []
    exemption_request: MentorshipApprovalDto | None = None


class ParticipantSearchDto(BaseDto):
    participant_rows: list[ParticipantRowDto]
    total: int


class UnregisteredRowDto(PersonRowDto):
    # Mentor before mentee, whatever order they were admitted in.
    admitted_roles: list[ParticipantRole]
    rounds_taken_part: int
    last_round_name: str | None


class UnregisteredSearchDto(BaseDto):
    rows: list[UnregisteredRowDto]
    total: int
