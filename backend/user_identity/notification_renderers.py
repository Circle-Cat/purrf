"""Renders the block-request events into (subject, HTML body).

Mirrors ``recruiting/notification_renderers.py``: the domain-neutral
``render_registry`` dispatches on ``EventEntity.event_type`` and this module
resolves the display fields.

Only the three request events are rendered, because only they have recipients.
The four state-change events (``user.blocked`` and friends) reach nobody by
design, so a renderer for them would be dead code.

Bodies carry no links: the backend holds no frontend base URL to build one
from, the same reason the recruiting and mentorship copy names its destination
in words instead. "Accounts" is the label verbatim from the admin navigation.

Free text written by a person -- a request's reason, a decision's note -- and
every resolved name is HTML-escaped before it reaches a body.

Importing this module registers every renderer. ``fast_app_factory`` imports it
once at startup for that side effect, alongside ``user_recipient_resolvers``.
"""

import html

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.name_utils import user_display_name
from backend.common.user_enums import UserEvent
from backend.entity.block_request_entity import BlockRequestEntity
from backend.entity.event_entity import EventEntity
from backend.entity.users_entity import UsersEntity
from backend.notification_management.render_registry import register_render

_FOOTER = (
    "<p>This is an automated message from Purrf. Please do not reply "
    "directly to this email as this inbox is not monitored.</p>"
)


async def _name_of(session: AsyncSession, user_id: int | None) -> str:
    """The display name for one person, or "" when there is nobody to name.

    Args:
        session (AsyncSession): Active database async session.
        user_id (int | None): The person to name.

    Returns:
        str: Their display name, or "" when the id is None or resolves to no
            row -- a request can outlive the account it names.
    """
    if user_id is None:
        return ""
    result = await session.execute(
        select(
            UsersEntity.first_name,
            UsersEntity.last_name,
            UsersEntity.preferred_name,
        ).where(UsersEntity.user_id == user_id)
    )
    row = result.one_or_none()
    if row is None:
        return ""
    first_name, last_name, preferred_name = row
    return user_display_name(
        first_name=first_name, last_name=last_name, preferred_name=preferred_name
    )


async def _request_of(session: AsyncSession, event: EventEntity):
    """The block request an event points at, or None if it cannot be read.

    Args:
        session (AsyncSession): Active database async session.
        event (EventEntity): The event being rendered.

    Returns:
        BlockRequestEntity | None: The row, or None.
    """
    request_id = event.details.get("requestId")
    if request_id is None:
        return None
    result = await session.execute(
        select(BlockRequestEntity).where(BlockRequestEntity.request_id == request_id)
    )
    return result.scalars().one_or_none()


def _person(name: str, fallback: str) -> str:
    """A name to put in a sentence, never a blank gap.

    Args:
        name (str): The resolved display name, possibly "".
        fallback (str): What to say instead when it is blank.

    Returns:
        str: Something a sentence can be built around, HTML-escaped.
    """
    return html.escape(name or fallback)


@register_render(UserEvent.BLOCK_REQUESTED)
async def _render_block_requested(session: AsyncSession, event: EventEntity):
    """Tell the named reviewer there is a decision waiting for them."""
    row = await _request_of(session, event)
    target = _person(await _name_of(session, event.subject_id), "a user")
    raiser = _person(
        await _name_of(session, row.raised_by if row else None), "a colleague"
    )
    reason = html.escape(row.reason if row else "")
    return (
        "A block request is waiting for your decision",
        f"<p>{raiser} has asked you to decide whether {target} should be "
        f"blocked from Purrf.</p>"
        f"<p>Reason given: {reason}</p>"
        "<p>Open the Accounts page in Purrf to approve or reject the "
        "request.</p>" + _FOOTER,
    )


@register_render(UserEvent.BLOCK_REQUEST_REASSIGNED)
async def _render_block_request_reassigned(session: AsyncSession, event: EventEntity):
    """Tell both reviewers where the request went.

    One body for both, because the two readers need the same fact and a
    per-recipient variant is not something ``render_registry`` can express --
    it renders once per event, not once per recipient.
    """
    row = await _request_of(session, event)
    target = _person(await _name_of(session, event.subject_id), "a user")
    reviewer = _person(
        await _name_of(session, row.reviewer_id if row else None), "someone else"
    )
    return (
        "A block request has been reassigned",
        f"<p>The block request about {target} is now with {reviewer}.</p>"
        "<p>If that is you, open the Accounts page in Purrf to decide it. "
        "If it is not, there is nothing left for you to do.</p>" + _FOOTER,
    )


@register_render(UserEvent.BLOCK_REQUEST_DECIDED)
async def _render_block_request_decided(session: AsyncSession, event: EventEntity):
    """Tell the person who asked what the answer was."""
    row = await _request_of(session, event)
    target = _person(await _name_of(session, event.subject_id), "a user")
    reviewer = _person(
        await _name_of(session, row.decided_by if row else None), "an administrator"
    )
    approved = bool(event.details.get("approved"))
    outcome = "approved" if approved else "rejected"
    consequence = (
        f"<p>{target} is now blocked from Purrf.</p>"
        if approved
        else f"<p>{target} has not been blocked.</p>"
    )
    note = row.decision_note if row else None
    note_html = f"<p>Note: {html.escape(note)}</p>" if note else ""
    return (
        f"Your block request was {outcome}",
        f"<p>{reviewer} has {outcome} the block request you raised about "
        f"{target}.</p>" + consequence + note_html + _FOOTER,
    )
