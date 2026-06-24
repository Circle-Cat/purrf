from datetime import datetime
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import ApplicationStage


class ApplicationSubmitDto(BaseRequestDto):
    """Request body for a candidate submitting an application."""

    form_answers: dict


class ApplicationDto(BaseDto):
    """Response shape for an application."""

    id: int
    user_id: int
    job_id: int
    round_id: int
    stage: ApplicationStage
    form_answers: dict | None = None
    snapshot: dict | None = None
    is_viewed: bool


class ApplicationBoardCardDto(ApplicationDto):
    """Board card: an application plus a read-time-computed freeze annotation."""

    freeze_until: datetime | None = None
