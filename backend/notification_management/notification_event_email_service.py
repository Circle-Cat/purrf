import html

from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.notification_entity import NotificationEntity
from backend.notification_management import render_registry

# Every notification email ends with a paragraph opening this way; the link
# goes just above it, so it is read before the "don't reply" note.
_FOOTER_START = "<p>This is an automated message from Purrf."


def with_link(body: str, url: str) -> str:
    """``body`` with an "Open in Purrf" paragraph linking to ``url``.

    Placed above the last footer paragraph, or at the end when the body has
    none.

    Args:
        body (str): The rendered HTML body.
        url (str): Absolute URL of the page to open.

    Returns:
        str: The body with the link paragraph added.
    """
    paragraph = f'<p><a href="{html.escape(url, quote=True)}">Open in Purrf</a></p>'
    at = body.rfind(_FOOTER_START)
    if at < 0:
        return body + paragraph
    return body[:at] + paragraph + body[at:]


class NotificationEventEmailService:
    """Turns one ``NotificationEntity`` into a sent email, or raises why not.

    This is the ``email_service`` :class:`DeliveryService` calls -- the
    piece the delivery brief calls "a renderer dispatched by event_type,
    handing off to the existing transport". It has three jobs, each of
    which can fail permanently (never worth retrying) or transiently
    (worth retrying): resolve the event behind the notification, render it
    through ``render_registry``, look up the recipient's address, then send
    through the underlying Gmail transport.
    """

    def __init__(
        self,
        user_emails_repository,
        email_service,
        event_repository,
        render=render_registry.render,
        link=None,
        app_origin=None,
    ):
        """
        Args:
            user_emails_repository (UserEmailsRepository): Resolves the
                recipient's contact address.
            email_service (NotificationEmailService): The Gmail transport.
                Its own ``send()`` swallows failures and returns ``bool``;
                this class re-raises so ``DeliveryService`` can tell
                "never" from "not right now" apart.
            event_repository (EventRepository): Reads the event the
                notification points at, which is what gets rendered.
            render: async ``(session, event) -> (subject, body)``. Defaults
                to :func:`render_registry.render`; overridable in tests so
                they don't need the full recruiting renderer registry.
            link: async ``(session, event, user_id) -> path | None``, where
                the recipient acts on the event. With ``app_origin``, a path
                becomes an "Open in Purrf" link in the body; either missing,
                or no path, and the email goes without one.
            app_origin (str | None): The app's origin, such as
                ``https://purrf.io``, that paths are appended to.
        """
        self.user_emails_repository = user_emails_repository
        self.email_service = email_service
        self.event_repository = event_repository
        self.render = render
        self.link = link
        self.app_origin = app_origin.rstrip("/") if app_origin else None

    async def send(
        self, session: AsyncSession, notification: NotificationEntity
    ) -> None:
        """Render and send ``notification``'s email.

        Args:
            session (AsyncSession): Active database async session.
            notification (NotificationEntity): The row being delivered.

        Raises:
            LookupError: The event's event_type has no renderer, or the
                recipient has no email on file -- both permanent, since
                neither can change on retry.
            RuntimeError: The underlying transport reported failure (e.g.
                Gmail down) -- ask the caller for a retry.
        """
        # event_id is NOT NULL and FK'd with ON DELETE CASCADE, so the row
        # cannot outlive the event it points at.
        event = await self.event_repository.get_by_id(session, notification.event_id)
        subject, body = await self.render(session, event)
        if self.link is not None and self.app_origin:
            path = await self.link(session, event, notification.user_id)
            if path:
                body = with_link(body, f"{self.app_origin}{path}")

        address = await self.user_emails_repository.get_contact_email(
            session, notification.user_id
        )
        if not address:
            raise LookupError(f"user {notification.user_id} has no email on file")

        sent = await self.email_service.send(address, subject, body)
        if not sent:
            raise RuntimeError(
                f"email transport reported failure for notification "
                f"{notification.notification_id}"
            )
