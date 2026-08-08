from datetime import datetime

from backend.dto.base_dto import BaseDto


class JobActivityDto(BaseDto):
    """One entry in a job posting's audit timeline, newest first.

    ``event_type`` is the recorded event's own type, domain prefix included:
    ``"recruiting.job_created"``, ``"recruiting.review_opened"`` (covering
    submit-for-review, request-close and request-reopen, distinguished by
    ``details.kind``), ``"recruiting.review_decided"`` (distinguished by
    ``details.decision``), or ``"recruiting.pending_edit_discarded"``.
    ``details`` is a free-form, event-type-specific payload — see each
    writer's call site for its exact shape. Mirrors ``ApplicationActivityDto``.

    ``actor_id`` is null when the system did it under its own rules rather
    than on someone's behalf; ``actor_name`` is null with it, and the reader
    words those entries impersonally. An actor who no longer resolves falls
    back to ``"User {id}"``, which is a different thing from nobody.
    """

    id: int
    event_type: str
    details: dict
    actor_id: int | None
    actor_name: str | None
    created_at: datetime
