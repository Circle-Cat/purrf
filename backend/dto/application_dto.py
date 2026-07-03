from datetime import datetime
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import ApplicationStage


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
    # stage, pending sub_status, current submission unfrozen).
    editable: bool = False
