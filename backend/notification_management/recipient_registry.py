from typing import Awaitable, Callable, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.event_entity import EventEntity

Resolver = Callable[[AsyncSession, EventEntity], Awaitable[Iterable[int]]]

_RESOLVERS: dict[str, tuple[str, Resolver]] = {}


def register_recipients(event_type: str, *, subject_type: str):
    """Register the resolver that decides who needs to know about ``event_type``.

    Recipients are derived at send time from data already in the database
    rather than stored in a subscription table -- there is exactly one place
    that can be wrong, instead of one per write site.

    Args:
        event_type (str): Domain-prefixed type, e.g. ``"recruiting.reassigned"``.
        subject_type (str): What ``event.subject_id`` must point at for this
            resolver to read it correctly, e.g. ``"application"``. Declared
            per resolver because one event type's subject is a job while
            another's is an application, and the ids are interchangeable
            integers.

    Returns:
        Callable: Decorator that registers the resolver and returns it unchanged.

    Raises:
        ValueError: If ``event_type`` already has a resolver. Two resolvers
            for one type means one of them silently never runs.
    """

    def decorate(resolver: Resolver) -> Resolver:
        if event_type in _RESOLVERS:
            raise ValueError(f"Duplicate recipient resolver for {event_type!r}")
        _RESOLVERS[event_type] = (subject_type, resolver)
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

    Raises:
        ValueError: If the event's ``subject_type`` is not what the resolver
            was registered for. The resolver would otherwise read
            ``subject_id`` as an id of the wrong table, which does not fail --
            it silently resolves an unrelated row's owners, or nobody.
    """
    registration = _RESOLVERS.get(event.event_type)
    if registration is None:
        return set()

    subject_type, resolver = registration
    if event.subject_type != subject_type:
        raise ValueError(
            f"{event.event_type!r} resolves recipients from a "
            f"{subject_type!r} subject, got {event.subject_type!r}"
        )
    return set(await resolver(session, event))
