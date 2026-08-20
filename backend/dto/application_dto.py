from datetime import datetime
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import (
    ApplicationLockReason,
    ApplicationStage,
    JobKind,
)
from backend.common.mentorship_enums import ParticipantRole


class ApplicationSubmitDto(BaseRequestDto):
    """Candidate submission payload (profile snapshot + custom answers)."""

    job_id: int
    personal: dict = {}
    education: list[dict] = []
    experience: list[dict] = []
    answers: dict = {}
    resume_sha256: str | None = None
    resume_object_key: str | None = None
    save_to_profile: bool = False


class ApplicationEditDto(BaseRequestDto):
    """Edit payload for an application still in Applied (no job change)."""

    personal: dict = {}
    education: list[dict] = []
    experience: list[dict] = []
    answers: dict = {}
    resume_sha256: str | None = None
    resume_object_key: str | None = None
    # Frontend-owned, same as on ApplicationSubmitDto above.
    save_to_profile: bool = False


class ApplicationSubmissionDto(BaseDto):
    """One submission version in a response."""

    version: int
    is_frozen: bool
    submission: dict | None = None
    resume_object_key: str | None = None
    resume_sha256: str | None = None
    submitted_at: datetime | None = None


class ApplicationDto(BaseDto):
    """Response shape for an application plus its current submission version."""

    id: int
    job_id: int
    user_id: int
    stage: ApplicationStage
    sub_status: str | None = None
    tags: dict | None = None
    current: ApplicationSubmissionDto | None = None
    # Whether the candidate may still edit this application (first pipeline
    # stage, pending sub_status, current submission unfrozen). Derived from
    # lock_reason, never set alongside it, so the two cannot disagree.
    editable: bool = False
    # Why editing is closed, for the candidate to read. None while editable.
    lock_reason: ApplicationLockReason | None = None
    # Which round of `stage` the applicant is on; meaningless (always 1)
    # for a stage configured with a single round.
    current_round: int = 1


class MyApplicationSummaryDto(BaseDto):
    """One row of the current user's own application list (any job kind)."""

    application_id: int
    job_id: int
    job_title: str
    job_kind: JobKind
    mentorship_role: ParticipantRole | None = None
    stage: ApplicationStage


class MyApplicationsDto(BaseDto):
    """The current user's own application list, plus every mentorship role
    those applications qualify them to register a round under.

    The set is resolved server-side rather than left for the caller to work
    out from the rows (see
    `ApplicationRepository.list_hired_activity_roles`). A client that
    filtered the rows itself would be free to disagree with the validation
    the registration endpoints actually apply.

    A set, not a single role: a user admitted to both a mentor and a mentee
    posting picks which one a given round is registered under, and nothing
    here decides it for them.

    The order carries no authority: it is most-recent-admission-first for
    display only, and no code may treat element 0 as "the" role.
    """

    applications: list[MyApplicationSummaryDto]
    # Every role the caller holds a HIRED mentor/mentee ACTIVITY application
    # in, most recent admission first for display only — this order carries
    # no authority, so no code may treat element 0 as "the" role. Empty when
    # they are not a participant.
    mentorship_roles: list[ParticipantRole] = []
