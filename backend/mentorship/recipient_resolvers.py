"""Who needs to know about each mentorship event.

Same derivation rule as ``recruiting/recipient_resolvers.py`` -- recipients
come from data already in the database, not a subscription table -- with one
difference that matters: this domain's recipient is a candidate, not staff.

Importing this module registers every resolver. ``fast_app_factory`` imports
it once at startup for that side effect.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import MentorshipEvent
from backend.entity.event_entity import EventEntity
from backend.notification_management.recipient_registry import register_recipients
from backend.repository.application_repository import ApplicationRepository

# Stateless, so one module-level instance serves every resolver.
_application_repository = ApplicationRepository()


@register_recipients(MentorshipEvent.MENTOR_ADMITTED, subject_type="application")
async def _admitted_applicant(session: AsyncSession, event: EventEntity) -> set[int]:
    """The admitted person, and nobody else.

    Staff are not recipients here: the accompanying
    ``recruiting.stage_changed`` already tells the pipeline that the
    application moved, and this event exists to reach the person outside the
    company.

    Safe only because the event is always recorded with ``actor_id=None``.
    ``record_event`` discards the actor from the recipients, and on the
    auto-hire paths the acting user *is* this applicant -- recording them as
    the actor would leave nobody to notify, silently.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The admission event; its subject is the
            application.

    Returns:
        set[int]: The applicant's user id, or empty if the application is gone.
    """
    application = await _application_repository.get_by_id(session, event.subject_id)
    return set() if application is None else {application.user_id}


@register_recipients(
    MentorshipEvent.MATCHING_RUN_COMPLETED, subject_type="mentorship_round"
)
async def _run_starter(session: AsyncSession, event: EventEntity) -> set[int]:
    """Whoever started the run, and nobody else.

    Read from the event's own details rather than looked up: nothing outside
    the run records who asked for it, and by the time this resolves, the run's
    Redis keys are not this function's to reach -- a resolver is handed a
    session and an event, which is the shape that keeps every domain's
    recipients answerable from the database.

    Safe only because the event is recorded with ``actor_id=None``.
    ``record_event`` discards the actor from the recipients, and the actor
    here would be the very person being told.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The completion event; its subject is the round.

    Returns:
        set[int]: The starter's user id, or empty when the run carried none --
            a run started by a tool rather than a person has nobody to tell.
    """
    del session
    raw = event.details.get("triggeredByUserId")
    if raw is None:
        return set()
    try:
        return {int(raw)}
    except (TypeError, ValueError):
        return set()
