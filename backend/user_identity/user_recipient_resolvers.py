"""Who needs to know about each user-subject event.

Same derivation rule as ``recruiting/recipient_resolvers.py``: recipients come
from rows already in the database, here the ``block_request`` row the event
points at, rather than from a subscription table.

🔴 **The target is never a recipient of any of these.** Blocking deliberately
discloses no reason to the person blocked -- they see the suspended page when
they next sign in -- and deactivation is by definition what the user themselves
asked for. Their own ``user_id`` is the event's ``subject_id``, so it would be
the easiest thing in the world to include by accident.

``user.blocked`` / ``unblocked`` / ``deactivated`` / ``reactivated`` register no
resolver at all. That is the supported way to say "timeline only" -- see
``recipient_registry.resolve_recipients``, which returns an empty set for an
unregistered type. A resolver that returned ``set()`` would say the same thing
less clearly and invite someone to "fix" it later.

Importing this module registers every resolver. ``fast_app_factory`` imports it
once at startup for that side effect.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.user_enums import USER_SUBJECT_TYPE, UserEvent
from backend.entity.block_request_entity import BlockRequestEntity
from backend.entity.event_entity import EventEntity
from backend.notification_management.recipient_registry import register_recipients


async def _request_of(session: AsyncSession, event: EventEntity):
    """The block request an event points at.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded.

    Returns:
        BlockRequestEntity: The row named by ``details["requestId"]``.

    Raises:
        ValueError: If the key is absent, or names no row. An event of this
            type without a resolvable request can only reach nobody, and this
            is the one place that can still say so out loud -- a write site
            that spells the key differently would otherwise notify no one, with
            no exception and no log.
    """
    request_id = event.details.get("requestId")
    if request_id is None:
        raise ValueError(f"{event.event_type!r} requires details['requestId']")
    result = await session.execute(
        select(BlockRequestEntity).where(
            BlockRequestEntity.request_id == request_id
        )
    )
    row = result.scalars().one_or_none()
    if row is None:
        raise ValueError(f"{event.event_type!r} names unknown request {request_id}")
    return row


@register_recipients(UserEvent.BLOCK_REQUESTED, subject_type=USER_SUBJECT_TYPE)
async def _named_reviewer(session: AsyncSession, event: EventEntity) -> set[int]:
    """The one person asked to decide it.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The ``user.block_requested`` event.

    Returns:
        set[int]: The named reviewer.
    """
    row = await _request_of(session, event)
    return {row.reviewer_id}


@register_recipients(
    UserEvent.BLOCK_REQUEST_REASSIGNED, subject_type=USER_SUBJECT_TYPE
)
async def _both_reviewers(session: AsyncSession, event: EventEntity) -> set[int]:
    """The new reviewer and the one it was taken from.

    The person losing it is told too: they may have already started looking
    into it, and a request that silently vanishes from their queue is worse
    than one they are told about.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The ``user.block_request_reassigned`` event.

    Returns:
        set[int]: Both reviewers. Just the new one if the event carries no
            previous reviewer.
    """
    row = await _request_of(session, event)
    previous = event.details.get("previousReviewerId")
    return {row.reviewer_id} | ({previous} if previous is not None else set())


@register_recipients(UserEvent.BLOCK_REQUEST_DECIDED, subject_type=USER_SUBJECT_TYPE)
async def _the_raiser(session: AsyncSession, event: EventEntity) -> set[int]:
    """The person who asked, now that there is an answer.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The ``user.block_request_decided`` event.

    Returns:
        set[int]: The raiser.
    """
    row = await _request_of(session, event)
    return {row.raised_by}
