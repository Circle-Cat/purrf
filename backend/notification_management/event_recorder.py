from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.event_entity import EventEntity
from backend.entity.notification_entity import NotificationEntity
from backend.notification_management.recipient_registry import resolve_recipients
from backend.repository.users_repository import UsersRepository

# Module level because ``record_event`` is a free function called from a dozen
# services, none of which owns this dependency; repositories hold no state of
# their own, so one instance is the same as any other.
_users_repository = UsersRepository()


async def record_event(
    session: AsyncSession,
    *,
    subject_type: str,
    subject_id: int,
    actor_id: int | None,
    event_type: str,
    details: dict | None = None,
    created_at: datetime | None = None,
) -> tuple[EventEntity, list[NotificationEntity]]:
    """Record what happened and fan it out to everyone who needs to know.

    Writes one ``event`` row and one ``notification`` row per recipient,
    all inside the caller's transaction, so the in-app bell is delivered
    atomically with the business change. Email is published separately,
    after commit, by the listener in ``publish_on_commit``.

    Two recipients are always subtracted from whatever the resolver returns:
    the actor, and anyone deactivated or blocked. Both states are refused at
    the door by ``AuthMiddleware``, so notifying one writes a bell nobody can
    read and mails a link its recipient cannot open. The event row itself is
    written either way -- the timeline records what happened regardless of
    who could be told about it.

    That filter lives here rather than inside each resolver for three
    reasons: this is the only caller of ``resolve_recipients``, so there is
    one place to be wrong instead of one per domain; a resolver's own
    emptiness stays meaningful (``recruiting._mentioned`` treats resolving to
    nobody as a write-site bug and raises, which a deactivated mentionee must
    not trigger); and "who is connected to this event" and "who can still
    receive anything" are different questions, the second belonging beside
    the existing actor subtraction.

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
        created_at (datetime | None): When it happened, if that is not now.
            An inbound email is found by a sweep some time after it arrived,
            and the timeline should read as the conversation ran, not as we
            noticed it. Defaults to the database's clock.

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
        **({"created_at": created_at} if created_at is not None else {}),
    )
    session.add(event)
    await session.flush()

    recipients = await resolve_recipients(session, event)
    recipients.discard(actor_id)
    recipients = await _users_repository.filter_reachable_ids(session, recipients)

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
