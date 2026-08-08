from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.event_entity import EventEntity

Renderer = Callable[[AsyncSession, EventEntity], Awaitable[tuple[str, str]]]

_RENDERERS: dict[str, Renderer] = {}


def register_render(event_type: str):
    """Register the function that renders ``event_type`` into an email.

    Mirrors ``recipient_registry.register_recipients``: one place per event
    type that can be wrong, instead of one per delivery path. Domain-neutral
    on purpose -- ``DeliveryService`` calls :func:`render` without knowing
    recruiting (or any other domain) exists.

    Args:
        event_type (str): Domain-prefixed type, e.g. ``"recruiting.reassigned"``.

    Returns:
        Callable: Decorator that registers the renderer and returns it
            unchanged.

    Raises:
        ValueError: If ``event_type`` already has a renderer. Two renderers
            for one type means one of them silently never runs.
    """

    def decorate(renderer: Renderer) -> Renderer:
        if event_type in _RENDERERS:
            raise ValueError(f"Duplicate email renderer for {event_type!r}")
        _RENDERERS[event_type] = renderer
        return renderer

    return decorate


async def render(session: AsyncSession, event: EventEntity) -> tuple[str, str]:
    """Render ``event`` into (subject, HTML body) using its registered renderer.

    Args:
        session (AsyncSession): Active database async session, for the
            renderer's own display-field lookups.
        event (EventEntity): The event the notification being delivered
            points at.

    Returns:
        tuple[str, str]: Subject line and HTML body.

    Raises:
        KeyError: If ``event.event_type`` has no registered renderer.
            Deliberately not a silent fallback -- a blank email is worse
            than a loud failure, and the exhaustiveness test that pairs
            every recipient-notifying event type with a renderer makes this
            unreachable in practice. ``KeyError`` is a ``LookupError``, so
            ``DeliveryService`` treats it the same as "no address on
            file": permanent, not worth retrying.
    """
    return await _RENDERERS[event.event_type](session, event)
