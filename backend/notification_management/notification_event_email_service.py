from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.event_entity import EventEntity
from backend.entity.notification_entity import NotificationEntity
from backend.notification_management import render_registry


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
        self, user_emails_repository, email_service, render=render_registry.render
    ):
        """
        Args:
            user_emails_repository (UserEmailsRepository): Resolves the
                recipient's contact address.
            email_service (NotificationEmailService): The Gmail transport.
                Its own ``send()`` swallows failures and returns ``bool``;
                this class re-raises so ``DeliveryService`` can tell
                "never" from "not right now" apart.
            render: async ``(session, event) -> (subject, body)``. Defaults
                to :func:`render_registry.render`; overridable in tests so
                they don't need the full recruiting renderer registry.
        """
        self.user_emails_repository = user_emails_repository
        self.email_service = email_service
        self.render = render

    async def send(
        self, session: AsyncSession, notification: NotificationEntity
    ) -> None:
        """Render and send ``notification``'s email.

        Args:
            session (AsyncSession): Active database async session.
            notification (NotificationEntity): The row being delivered.

        Raises:
            LookupError: The notification's event is gone, its event_type
                has no renderer, or the recipient has no email on file --
                all permanent, since none can change on retry.
            RuntimeError: The underlying transport reported failure (e.g.
                Gmail down) -- ask the caller for a retry.
        """
        event = await session.get(EventEntity, notification.event_id)
        if event is None:
            raise LookupError(
                f"notification {notification.notification_id} has no event "
                f"(event_id={notification.event_id!r})"
            )
        subject, body = await self.render(session, event)

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
