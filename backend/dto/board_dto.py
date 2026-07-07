"""Board-facing DTOs for the recruiting application board (PR2).

Holds the projections the board surfaces (job switcher entries, applicant
cards). Grows request DTOs (stage moves, etc.) in later tasks of this
sub-project.
"""

from datetime import datetime

from pydantic import field_validator, model_validator

from backend.dto.application_dto import ApplicationDto
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import ApplicationStage, JobKind

# Fixed reject-reason list surfaced by the board's reject dialog. A reject
# stage change must supply one of these (see StageChangeDto's validator).
REJECT_REASONS = (
    "Insufficient experience",
    "Did not meet the technical bar",
    "Communication concerns",
    "Not aligned with our mission",
    "Accepted another offer",
    "Incomplete application",
    "Candidate declined the offer",
    "Other",
)


class PipelineStageInfoDto(BaseDto):
    """One of a job's configured pipeline stages, for the board's lane list."""

    stage: str
    rounds: int


class BoardJobDto(BaseDto):
    """A job the caller owns, for the board's job switcher."""

    id: int
    title: str
    kind: JobKind
    stages: list[PipelineStageInfoDto]  # configured stages + rounds, in global order


class BoardCardDto(BaseDto):
    """One applicant card on the board."""

    id: int  # application id
    applicant_name: str
    applicant_email: str
    stage: ApplicationStage
    sub_status: str | None = None
    tags: dict | None = None
    applied_at: datetime | None = None
    round: int = 1
    # Whether the applicant is CURRENTLY blocked org-wide (distinct from
    # tags["blacklisted"], which just records that this application was
    # rejected by a blacklist action at some point and never changes after).
    is_blocked: bool = False
    # The interviewer responsible for this card's current stage+round, for
    # interview-stage cards only (None for e.g. applied/offer/hired/rejected
    # — the board never renders a reviewer line for those). None also means
    # "nobody assigned yet" for an interview-stage card.
    reviewer_name: str | None = None


class ApplicationDetailDto(BaseDto):
    """Owner-facing full view of one application."""

    application: ApplicationDto
    applicant_name: str
    applicant_email: str
    resume_available: bool
    form_schema: dict | None = (
        None  # the job's LIVE form_schema, so the dialog can label answers
    )
    # Role signals for the shared detail page (sub-project #3 slice 1): lets
    # the frontend decide which of the owner-decision area / evaluator-rubric
    # area to render, without a second round-trip.
    is_owner: bool = False
    assignee_id: int | None = None


class ApplicationActivityDto(BaseDto):
    """One entry in an application's owner-facing audit timeline, newest first.

    ``event_type`` is one of ``"application_submitted"``, ``"auto_rejected"``
    (both written by ``ApplicationService.submit``), or ``"stage_changed"``,
    ``"reassigned"``, ``"round_advanced"`` (written by the matching
    ``BoardService`` methods). ``details`` is a free-form, event-type-specific
    payload — see each writer's call site for its exact shape.
    """

    id: int
    event_type: str
    details: dict
    actor_id: int
    actor_name: str
    created_at: datetime


class StageChangeDto(BaseRequestDto):
    """Advance or reject one application."""

    to_stage: ApplicationStage
    reason: str | None = None
    note: str | None = None
    # Required when to_stage is an interview stage (screening/behavioral/
    # tech/board_review); ignored for terminal targets (hired/rejected).
    assignee_id: int | None = None

    @model_validator(mode="after")
    def reason_required_for_reject(self) -> "StageChangeDto":
        """Reject moves must carry a reason from the fixed REJECT_REASONS list."""
        if self.to_stage == ApplicationStage.REJECTED:
            if self.reason not in REJECT_REASONS:
                raise ValueError("a reject reason from the fixed list is required")
        return self


class SubStatusChangeDto(BaseRequestDto):
    """Manual sub-status switch within the current stage."""

    sub_status: str


class ReassignDto(BaseRequestDto):
    """Change who is responsible for an application's current stage."""

    assignee_id: int


class RoundChangeDto(BaseRequestDto):
    """Advance an application to a specific round within its current stage."""

    round: int
    # Optional even for an interview stage (INTERVIEW_STAGES in
    # board_service.py) -- a round can be left unassigned, to be picked up
    # later via reassign. Ignored entirely for a non-interview stage, e.g.
    # a multi-round OFFER stage, which has no rubric and is not assignable.
    assignee_id: int | None = None

    @field_validator("round")
    @classmethod
    def round_positive(cls, v: int) -> int:
        """Require at least round 1.

        Args:
            v (int): The candidate round number.

        Returns:
            int: The validated round number.

        Raises:
            ValueError: If less than 1.
        """
        if v < 1:
            raise ValueError("round must be >= 1")
        return v


class BlacklistDto(BaseRequestDto):
    """Block a user org-wide and close out the triggering application."""

    user_id: int
    application_id: int
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        """A blacklist action must always carry a non-empty reason."""
        if not value.strip():
            raise ValueError("a reason is required")
        return value
