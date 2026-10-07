"""Renders operations events into (subject, HTML body).

Importing this module registers every renderer. ``fast_app_factory`` imports it
once at startup for that side effect.
"""

import html

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.ops_enums import OpsEvent
from backend.entity.event_entity import EventEntity
from backend.notification_management.render_registry import register_render

_FOOTER = (
    "<p>This is an automated message from Purrf. Please do not reply "
    "directly to this email as this inbox is not monitored.</p>"
)

_TITLES = {
    "watch_renewal_failed": "watch renewal failed",
    "history_expired": "history expired, full resync started",
    "sync_failed": "sync failed",
    "unrouted_mail": "new mail matched no Inbox alias",
}


@register_render(OpsEvent.GMAIL_SYNC_ALERT)
async def _render_gmail_sync_alert(session: AsyncSession, event: EventEntity):
    """Tell an ops.maintain holder what the Gmail sync tripped over.

    Everything rendered comes from ``event.details``; the detail is free text
    from an exception and is HTML-escaped.
    """
    del session
    details = event.details
    kind = details.get("kind")
    title = _TITLES.get(kind, kind or "unknown")
    advice = "Check the backend logs for [GmailSync]."
    if kind == "watch_renewal_failed":
        advice += " Without a renewed watch, new mail stops arriving within seven days."
    return (
        f"Gmail sync: {title}",
        f"<p>The Gmail sync for {html.escape(details.get('mailbox', ''))} "
        f"needs attention: {html.escape(title)}.</p>"
        f"<p>Detail: {html.escape(details.get('detail', ''))}</p>"
        f"<p>{advice}</p>" + _FOOTER,
    )
