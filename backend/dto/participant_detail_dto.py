"""What the admin console's page for one person in one round reads and
writes."""

from datetime import datetime

from pydantic import Field

from backend.common.mentorship_enums import ParticipantNoteTag
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.dto.block_dto import PendingBlockRequestDto
from backend.dto.mentorship_approval_dto import ApprovalPairDto, ApprovalPersonDto
from backend.dto.participant_search_dto import ParticipantRowDto, PersonRowDto
from backend.dto.round_feedback_dto import ParticipantFeedbackDto

NOTE_MAX_LENGTH = 5000


class DetailRoundDto(BaseDto):
    round_id: int
    name: str
    required_meetings: int | None = None
    # Writes on the page are offered only while this is true.
    in_progress: bool


class ParticipantNoteDto(BaseDto):
    note_id: int
    tag: ParticipantNoteTag | None = None
    body: str
    pair_id: int | None = None
    # Set when an approval wrote the note.
    request_id: int | None = None
    author: ApprovalPersonDto
    created_at: datetime


class PendingRequestDto(BaseDto):
    """A request about this person in this round waiting on a reviewer. Who
    raised it is included: only they may withdraw or reassign it."""

    request_id: int
    action: str
    raised_by: ApprovalPersonDto
    reviewer: ApprovalPersonDto
    pair_id: int | None = None
    pair: ApprovalPairDto | None = None
    reason: str | None = None
    created_at: datetime | None = None


class ParticipationHistoryRowDto(ParticipantRowDto):
    exempted: bool


class ParticipantDetailDto(BaseDto):
    person: PersonRowDto
    round: DetailRoundDto
    # None when the person has not registered for the round.
    registration: ParticipantRowDto | None = None
    exempted: bool
    # None when the round asks no feedback of them: they had no pair in it.
    feedback: ParticipantFeedbackDto | None = None
    notes: list[ParticipantNoteDto]
    pending_block_request: PendingBlockRequestDto | None = None
    pending_requests: list[PendingRequestDto]
    # Rounds they registered for that ended before this one, newest first.
    history: list[ParticipationHistoryRowDto]


class ParticipantNoteCreateDto(BaseRequestDto):
    body: str = Field(min_length=1, max_length=NOTE_MAX_LENGTH)
