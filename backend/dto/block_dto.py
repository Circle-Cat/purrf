"""DTOs for blocking: the request-and-approval flow and the direct action."""

from datetime import datetime

from pydantic import field_validator

from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto


class BlockPreflightDto(BaseDto):
    """What applying a block will actually do. Counts and dates only -- which
    job someone applied to is content, not state, and is not the operator's
    to see."""

    application_count: int
    interview_times: list[datetime]


class BlockRequestDto(BaseDto):
    """One block request, named people resolved for display."""

    id: int
    target_user_id: int
    target_name: str
    raised_by: int
    raised_by_name: str
    raised_from: str
    raised_at: datetime
    reason: str
    reviewer_id: int
    reviewer_name: str
    status: str  # pending | approved | rejected | superseded
    decided_by: int | None = None
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None


class DeactivateRequestDto(BaseRequestDto):
    """Deactivate an account. The note is optional: deactivation is not a
    finding of fault, unlike blocking."""

    note: str | None = None


class BlockRequestCreateDto(BaseRequestDto):
    """Ask a named reviewer to block someone."""

    user_id: int
    reason: str
    reviewer_id: int

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        """A block request must always carry a non-empty reason."""
        if not value.strip():
            raise ValueError("a reason is required")
        return value


class BlockDirectDto(BaseRequestDto):
    """Block someone without going through a request."""

    reason: str

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        """A block action must always carry a non-empty reason."""
        if not value.strip():
            raise ValueError("a reason is required")
        return value


class BlockDecideDto(BaseRequestDto):
    """The named reviewer's decision on a pending request."""

    approved: bool
    note: str | None = None


class BlockReassignDto(BaseRequestDto):
    """Hand a pending request to a different reviewer. Done by the raiser."""

    reviewer_id: int
