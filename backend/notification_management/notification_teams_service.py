import html
import os

import httpx
from azure.identity.aio import WorkloadIdentityCredential
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.constants import MICROSOFT_AAD_ID_BY_LDAP_KEY, ldap_from_addresses
from backend.common.environment_constants import AZURE_TENANT_ID, TEAMS_BOT_APP_ID
from backend.entity.notification_entity import NotificationEntity
from backend.notification_management.notification_event_email_service import (
    without_footer,
)
from backend.notification_management.teams_message_service import TeamsMessageService

# Each Bot Connector call is made while a Pub/Sub push waits for its answer.
_BOT_CONNECTOR_TIMEOUT_SECONDS = 10.0


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
        message = (
            f"<p><strong>{html.escape(subject)}</strong></p>{without_footer(body)}"
        )
        await self.teams_message_service.send(aad_id, message)


def build_notification_teams_service(
    logger, user_emails_repository, redis_client, compose
) -> NotificationTeamsService | None:
    """The Teams service for this environment, or None when it has no bot.

    The bot signs in through the pod's workload identity, which also supplies
    the tenant and the federated token file.

    Args:
        logger: Logger instance.
        user_emails_repository (UserEmailsRepository): See NotificationTeamsService.
        redis_client: See NotificationTeamsService.
        compose: See NotificationTeamsService.

    Returns:
        NotificationTeamsService | None: None unless ``TEAMS_BOT_APP_ID`` is set.
    """
    app_id = (os.getenv(TEAMS_BOT_APP_ID) or "").strip()
    if not app_id:
        return None
    sender = TeamsMessageService(
        logger=logger,
        app_id=app_id,
        tenant_id=os.getenv(AZURE_TENANT_ID),
        credential=WorkloadIdentityCredential(client_id=app_id),
        http_client=httpx.AsyncClient(timeout=_BOT_CONNECTOR_TIMEOUT_SECONDS),
    )
    return NotificationTeamsService(
        logger=logger,
        user_emails_repository=user_emails_repository,
        redis_client=redis_client,
        compose=compose,
        teams_message_service=sender,
    )
