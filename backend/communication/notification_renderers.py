"""Renders Inbox events into (subject, HTML body).

Importing this module registers every renderer. ``fast_app_factory`` imports it
once at startup for that side effect. Bodies carry no links and point at the
sidebar label "Inbox"; every value from mail is HTML-escaped.
"""

import html

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.communication_enums import InboxService
from backend.common.inbox_enums import InboxEvent
from backend.entity.event_entity import EventEntity
from backend.notification_management.render_registry import register_render

_FOOTER = (
    "<p>This is an automated message from Purrf. Please do not reply "
    "directly to this email as this inbox is not monitored.</p>"
)

_SERVICE_NAMES = {
    InboxService.MENTORSHIP: "Mentorship",
    InboxService.RECRUITING: "Recruiting",
    InboxService.INQUIRIES: "Inquiries",
}


def _e(value):
    return html.escape(value or "")


@register_render(InboxEvent.NEEDS_REPLY)
async def _render_needs_reply(session: AsyncSession, event: EventEntity):
    """Tell a service's people that a new email is waiting for a reply."""
    del session
    details = event.details
    service = details.get("service")
    name = _SERVICE_NAMES.get(service, service)
    return (
        "New email needs a reply",
        f"<p>A new email in the {_e(name)} inbox needs a reply: "
        f"“{_e(details.get('subject'))}” from {_e(details.get('from'))}.</p>"
        "<p>Open Inbox in Purrf to read and reply.</p>" + _FOOTER,
    )


@register_render(InboxEvent.BOUNCED)
async def _render_bounced(session: AsyncSession, event: EventEntity):
    """Tell the sender that their email did not arrive."""
    del session
    details = event.details
    return (
        "Your email was not delivered",
        f"<p>Your email to {_e(details.get('bouncedTo'))} about "
        f"“{_e(details.get('subject'))}” was not delivered.</p>"
        "<p>Open Inbox in Purrf to see the thread.</p>" + _FOOTER,
    )
