"""Board-facing DTOs for the recruiting application board (PR2).

Holds the projections the board surfaces (job switcher entries, applicant
cards). Grows request DTOs (stage moves, etc.) in later tasks of this
sub-project.
"""

from datetime import datetime

from pydantic import model_validator

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
    "Other",
)


class BoardJobDto(BaseDto):
    """A job the caller owns, for the board's job switcher."""

    id: int
    title: str
    kind: JobKind
    stages: list[str]  # configured stage values in global order


class BoardCardDto(BaseDto):
    """One applicant card on the board."""

    id: int  # application id
    applicant_name: str
    applicant_email: str
    stage: ApplicationStage
    sub_status: str | None = None
    tags: dict | None = None
    applied_at: datetime | None = None


class ApplicationDetailDto(BaseDto):
    """Owner-facing full view of one application."""

    application: ApplicationDto
    applicant_name: str
    applicant_email: str
    resume_available: bool
    form_schema: dict | None = (
        None  # the job's LIVE form_schema, so the dialog can label answers
    )


class StageChangeDto(BaseRequestDto):
    """Advance or reject one application."""

    to_stage: ApplicationStage
    reason: str | None = None
    note: str | None = None

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
