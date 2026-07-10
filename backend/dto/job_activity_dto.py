from datetime import datetime

from backend.dto.base_dto import BaseDto


class JobActivityDto(BaseDto):
    """One entry in a job posting's audit timeline, newest first.

    ``event_type`` is one of ``"job_created"`` (written by
    ``JobService.create_job``), ``"review_opened"`` (written by
    ``JobService._open_review``, covering submit-for-review, request-close,
    and request-reopen — distinguished by ``details.kind``), or
    ``"review_decided"`` (written by ``JobService.approve``/``reject``,
    distinguished by ``details.decision``). ``details`` is a free-form,
    event-type-specific payload — see each writer's call site for its exact
    shape. Mirrors ``ApplicationActivityDto``.
    """

    id: int
    event_type: str
    details: dict
    actor_id: int
    actor_name: str
    created_at: datetime
