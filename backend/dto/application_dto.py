import re
from datetime import datetime
from pydantic import model_validator
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import (
    ApplicationLockReason,
    ApplicationStage,
    JobKind,
)
from backend.common.mentorship_enums import ParticipantRole


_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class _ResumeReferenceDto(BaseRequestDto):
    """The résumé a submission points at, as the upload endpoint returned it.

    Upload stores the file at ``resumes/<sha256>.pdf`` and hands both values
    back, so a key is only accepted alongside the hash it was stored under.
    Anything else would point a reviewer at an object nobody uploaded for this
    application. Either field may be cleared on its own: the service drops both
    for a posting that collects no résumé, one assignment at a time.
    """

    resume_sha256: str | None = None
    resume_object_key: str | None = None

    @model_validator(mode="after")
    def check_resume_reference(self):
        if self.resume_object_key is None:
            return self
        if self.resume_sha256 is None or not _SHA256_HEX.fullmatch(self.resume_sha256):
            raise ValueError("A resume needs the sha256 it was uploaded with")
        if self.resume_object_key != f"resumes/{self.resume_sha256}.pdf":
            raise ValueError("The resume key does not match its sha256")
        return self


class ApplicationSubmitDto(_ResumeReferenceDto):
    """Candidate submission payload (profile snapshot + custom answers)."""

    job_id: int
    personal: dict = {}
    education: list[dict] = []
    experience: list[dict] = []
    answers: dict = {}
    save_to_profile: bool = False


class ApplicationEditDto(_ResumeReferenceDto):
    """Edit payload for an application still in Applied (no job change)."""

    personal: dict = {}
    education: list[dict] = []
    experience: list[dict] = []
    answers: dict = {}
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
