from datetime import datetime
from typing import Literal

from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import JobReviewKind, JobReviewStatus


class JobSubmitDto(BaseRequestDto):
    """Request body for submitting a job for review."""

    reviewer_id: int
    message: str | None = None


class JobReviewDecisionDto(BaseRequestDto):
    """Request body for a reviewer's approve/reject decision."""

    decision: Literal["approve", "reject"]
    comment: str | None = None


class JobReviewDto(BaseDto):
    """Response shape for a single review cycle."""

    review_id: int
    job_id: int
    submitted_by: int
    reviewer_id: int
    status: JobReviewStatus
    kind: JobReviewKind
    submit_message: str | None = None
    reject_comment: str | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None


class ApproverDto(BaseDto):
    """A user eligible to approve job postings."""

    user_id: int
    name: str
    email: str
