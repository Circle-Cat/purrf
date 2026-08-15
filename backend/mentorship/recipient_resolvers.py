"""Who needs to know about each mentorship event.

Same derivation rule as ``recruiting/recipient_resolvers.py`` -- recipients
come from data already in the database, not a subscription table -- with one
difference that matters: this domain's recipient is a candidate, not staff.

Importing this module registers every resolver. ``fast_app_factory`` imports
it once at startup for that side effect.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import MentorshipEvent
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.notification_management.recipient_registry import register_recipients


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
    result = await session.execute(
        select(ApplicationEntity.user_id).where(
            ApplicationEntity.application_id == event.subject_id
        )
    )
    user_id = result.scalar_one_or_none()
    return set() if user_id is None else {user_id}
