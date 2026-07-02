"""Board-facing DTOs for the recruiting application board (PR2).

Holds the projections the board surfaces (job switcher entries, applicant
cards). Grows request DTOs (stage moves, etc.) in later tasks of this
sub-project.
"""

from datetime import datetime

from backend.dto.application_dto import ApplicationDto
from backend.dto.base_dto import BaseDto
from backend.common.recruiting_enums import ApplicationStage, JobKind


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
