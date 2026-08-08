from typing import Awaitable, Callable, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.event_entity import EventEntity

Resolver = Callable[[AsyncSession, EventEntity], Awaitable[Iterable[int]]]

_RESOLVERS: dict[str, Resolver] = {}


def register_recipients(event_type: str):
    """Register the resolver that decides who needs to know about ``event_type``.

    Recipients are derived at send time from data already in the database
    rather than stored in a subscription table -- there is exactly one place
    that can be wrong, instead of one per write site.

    Args:
        event_type (str): Domain-prefixed type, e.g. ``"recruiting.reassigned"``.

    Returns:
        Callable: Decorator that registers the resolver and returns it unchanged.

    Raises:
        ValueError: If ``event_type`` already has a resolver. Two resolvers
            for one type means one of them silently never runs.
    """

    def decorate(resolver: Resolver) -> Resolver:
        if event_type in _RESOLVERS:
            raise ValueError(f"Duplicate recipient resolver for {event_type!r}")
        _RESOLVERS[event_type] = resolver
        return resolver

    return decorate


async def resolve_recipients(session: AsyncSession, event: EventEntity) -> set[int]:
    """Return the user ids that should be notified about ``event``.

    An event type with no registered resolver yields an empty set. That is
    the supported way to say "this belongs on the timeline but nobody needs
    a notification" -- there is no separate ``should_notify`` switch.

    Args:
        session (AsyncSession): Session inside the caller's open transaction,
            so the resolver sees the business change that just happened.
        event (EventEntity): The event being recorded.

    Returns:
        set[int]: User ids, de-duplicated. Empty if nobody needs to know.
    """
    resolver = _RESOLVERS.get(event.event_type)
    if resolver is None:
        return set()
    return set(await resolver(session, event))
