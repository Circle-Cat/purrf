from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import JobKind, JobStatus
from backend.common.mentorship_enums import ParticipantRole


class JobCreateDto(BaseRequestDto):
    """Request body for creating/updating a posting (incl. form schema)."""

    title: str
    description: str | None = None
    kind: JobKind = JobKind.ACTIVITY
    mentorship_role: ParticipantRole | None = None
    form_schema: dict | None = None
    pipeline_config: list | None = None


class JobDto(BaseDto):
    """Response shape for a posting."""

    id: int
    title: str
    description: str | None = None
    kind: JobKind
    mentorship_role: ParticipantRole | None = None
    status: JobStatus
    form_schema: dict | None = None
    pipeline_config: list | None = None
    pending_form_schema: dict | None = None
    pending_pipeline_config: list | None = None
    last_reject_comment: str | None = None
    was_published: bool = False
