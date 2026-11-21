from urllib.parse import quote

import httpx

BOT_FRAMEWORK_SCOPE = "https://api.botframework.com/.default"
DEFAULT_SERVICE_URL = "https://smba.trafficmanager.net/teams/"

# Opening a chat fails this way when the user has not installed the bot's
# Teams app, or is not in the tenant at all. Neither changes on retry.
_NO_CHAT_STATUSES = {403, 404}


class TeamsMessageService:
    """Sends a Teams direct message as the Purrf bot, through the Bot Connector.

    The bot may message someone without them writing to it first, as long as
    they have its Teams app installed. Teams returns the same conversation for
    the same bot and user, so it is opened on every send rather than stored.
    """

    def __init__(
        self,
        logger,
        app_id: str,
        tenant_id: str,
        credential,
        http_client: httpx.AsyncClient,
        service_url: str = DEFAULT_SERVICE_URL,
    ):
        """
        Args:
            logger: Logger instance.
            app_id (str): Application (client) id of the bot.
            tenant_id (str): Tenant the bot and the recipients belong to.
            credential: Async credential with ``get_token(scope)``, signing in
                as the bot.
            http_client (httpx.AsyncClient): Client for the Bot Connector calls.
            service_url (str): Bot Connector base URL for Teams.
        """
        self.logger = logger
        self.app_id = app_id
        self.tenant_id = tenant_id
        self.credential = credential
        self.http_client = http_client
        self.service_url = service_url.rstrip("/")

    async def send(self, aad_object_id: str, html: str) -> None:
        """Message ``aad_object_id`` with ``html``.

        Args:
            aad_object_id (str): The recipient's Microsoft Entra object id.
            html (str): Message body, in the HTML subset Teams renders.

        Raises:
            LookupError: The bot cannot open a chat with this user, e.g. the
                app is not installed for them.
            RuntimeError: The Bot Connector answered with any other error.
        """
        token = await self.credential.get_token(BOT_FRAMEWORK_SCOPE)
        headers = {"Authorization": f"Bearer {token.token}"}

        opened = await self.http_client.post(
            f"{self.service_url}/v3/conversations",
            headers=headers,
            json={
                "bot": {"id": f"28:{self.app_id}"},
                "members": [{"id": aad_object_id}],
                "channelData": {"tenant": {"id": self.tenant_id}},
                "isGroup": False,
            },
        )
        if opened.status_code in _NO_CHAT_STATUSES:
            raise LookupError(
                f"bot cannot open a chat with {aad_object_id}: {opened.status_code}"
            )
        if not opened.is_success:
            raise RuntimeError(f"opening a Teams chat failed: {opened.status_code}")

        conversation_id = quote(opened.json()["id"], safe=":@")
        posted = await self.http_client.post(
            f"{self.service_url}/v3/conversations/{conversation_id}/activities",
            headers=headers,
            json={"type": "message", "textFormat": "xml", "text": html},
        )
        if not posted.is_success:
            raise RuntimeError(f"posting a Teams message failed: {posted.status_code}")
