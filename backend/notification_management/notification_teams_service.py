import html

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.constants import MICROSOFT_AAD_ID_BY_LDAP_KEY, ldap_from_addresses
from backend.entity.notification_entity import NotificationEntity
from backend.notification_management.notification_event_email_service import (
    without_footer,
)


class NotificationTeamsService:
    """Sends internal staff a Teams copy of a notification's email.

    Only someone with a confirmed company address is internal here; an
    unconfirmed one could be anybody's claim to that employee's inbox. Their
    Microsoft object id comes from the hash the daily member sync writes, so a
    person who joined since the last sync gets the email only.
    """

    def __init__(
        self,
        logger,
        user_emails_repository,
        redis_client,
        compose,
        teams_message_service,
    ):
        """
        Args:
            logger: Logger instance.
            user_emails_repository (UserEmailsRepository): The recipient's
                addresses.
            redis_client: Synchronous Redis client holding
                ``MICROSOFT_AAD_ID_BY_LDAP_KEY``.
            compose: async ``(session, notification) -> (subject, body)``,
                the email's own rendering.
            teams_message_service (TeamsMessageService): Sends the message.
        """
        self.logger = logger
        self.user_emails_repository = user_emails_repository
        self.redis_client = redis_client
        self.compose = compose
        self.teams_message_service = teams_message_service

    async def send(
        self, session: AsyncSession, notification: NotificationEntity
    ) -> None:
        """Message the recipient on Teams, or do nothing if they are not staff.

        Args:
            session (AsyncSession): Active database async session.
            notification (NotificationEntity): The row being delivered.

        Raises:
            LookupError: The bot cannot open a chat with the recipient.
            RuntimeError: The Bot Connector failed.
        """
        rows = await self.user_emails_repository.list_by_user_id(
            session, notification.user_id
        )
        ldap = ldap_from_addresses(row.email for row in rows if row.otp_confirmed)
        if ldap is None:
            return

        aad_id = self.redis_client.hget(MICROSOFT_AAD_ID_BY_LDAP_KEY, ldap)
        if not aad_id:
            self.logger.info(
                "[Teams] no Microsoft id for %s; notification %s goes by email only",
                ldap,
                notification.notification_id,
            )
            return
        if isinstance(aad_id, bytes):
            aad_id = aad_id.decode()

        subject, body = await self.compose(session, notification)
        message = f"<p><strong>{html.escape(subject)}</strong></p>{without_footer(body)}"
        await self.teams_message_service.send(aad_id, message)
