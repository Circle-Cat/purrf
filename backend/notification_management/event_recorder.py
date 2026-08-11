from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.event_entity import EventEntity
from backend.entity.notification_entity import NotificationEntity
from backend.notification_management.recipient_registry import resolve_recipients


async def record_event(
    session: AsyncSession,
    *,
    subject_type: str,
    subject_id: int,
    actor_id: int | None,
    event_type: str,
    details: dict | None = None,
) -> tuple[EventEntity, list[NotificationEntity]]:
    """Record what happened and fan it out to everyone who needs to know.

    Writes one ``event`` row and one ``notification`` row per recipient,
    all inside the caller's transaction, so the in-app bell is delivered
    atomically with the business change. Email is published separately,
    after commit, by the listener in ``publish_on_commit``.

    **Call this after the business change is written, never before.** The
    resolver queries the database through this same session, so it sees the
    transaction as it stands right now. Recording a reassignment before the
    assignment row is written means the resolver cannot see the new
    assignee, and that person silently never hears about it.

    Args:
        session (AsyncSession): Session inside an open transaction.
        subject_type (str): What the event is about, e.g. ``"application"``.
        subject_id (int): Primary key of that subject.
        actor_id (int | None): Who did it, excluded from the recipients.
            ``None`` when the system did it under its own rules rather than
            on someone's behalf -- an automatic rejection or assignment is
            nobody's action, and the copy words it that way. Passing the
            requesting user for those would name the candidate as the actor.
        event_type (str): Domain-prefixed type, e.g. ``"recruiting.reassigned"``.
        details (dict | None): Extra payload for rendering. Defaults to ``{}``.

    Returns:
        tuple[EventEntity, list[NotificationEntity]]: The event, and the
            notification rows created for it (empty when nobody needs to know).
    """
    event = EventEntity(
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=actor_id,
        event_type=event_type,
        details=details or {},
    )
    session.add(event)
    await session.flush()

    recipients = await resolve_recipients(session, event)
    recipients.discard(actor_id)

    notifications = [
        NotificationEntity(user_id=user_id, event_id=event.event_id)
        for user_id in sorted(recipients)
    ]
    session.add_all(notifications)
    if notifications:
        await session.flush()

    if notifications:
        session.info.setdefault("pending_notification_ids", []).extend(
            notification.notification_id for notification in notifications
        )

    return event, notifications
