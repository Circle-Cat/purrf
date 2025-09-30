from http import HTTPStatus


class GerritSubscriptionService:
    """
    Registers a webhook in Gerrit's Webhooks plugin.

    Uses the REST API:
    PUT /a/config/server/webhooks~projects/{project}/remotes/{remote}

    The webhook will send Gerrit events to the configured target URL.
    Handles "already exists" responses by retrieving the existing configuration.
    """

    def __init__(
        self,
        logger,
        gerrit_client,
        project: str,
        remote_name: str,
        subscribe_url: str,
        events: list[str],
    ):
        """
        Initializes the GerritSubscriptionService with fully injected parameters.

        Args:
            logger: Logger instance.
            gerrit_client: Gerrit client instance with 'base_url' and 'session'.
            project (str): Gerrit project to register the webhook for.
            remote_name (str): Identifier for the webhook in Gerrit.
            subscribe_url (str): The URL to which Gerrit will send webhook events.
            events (list[str]): List of Gerrit events to subscribe to.

        Raises:
            ValueError: If required parameters are missing or invalid.
        """
        self.logger = logger
        self.gerrit_client = gerrit_client
        self.project = project
        self.remote_name = remote_name
        self.subscribe_url = subscribe_url
        self.events = events

        if not self.logger:
            raise ValueError("A valid logger instance is required.")
        if not self.gerrit_client:
            raise ValueError("A valid Gerrit client instance is required.")
        if not self.project:
            raise ValueError("A valid project name is required.")
        if not self.remote_name:
            raise ValueError("A valid remote name is required.")
        if not self.subscribe_url:
            raise ValueError("A valid target URL is required.")
        if not self.events:
            raise ValueError("At least one event is required.")

        self.base_url = self.gerrit_client.base_url.rstrip("/")
        self.session = self.gerrit_client.session

        logger.debug(
            f"[GerritSubscriptionService] Subscribing to events: {self.events} "
            f"for project: {self.project}, sending to: {self.subscribe_url}"
        )

    def register_webhook(self) -> dict:
        """
        Registers (or ensures) the webhook subscription exists.
        Returns the subscription details as a dict.
        """
        api_path = f"/a/config/server/webhooks~projects/{self.project}/remotes/{self.remote_name}"
        url = self.base_url + api_path

        payload = {
            "url": self.subscribe_url,
            "events": self.events,
        }

        headers = {"Content-Type": "application/json; charset=UTF-8"}
        response = self.session.put(url, json=payload, headers=headers)

        if response.status_code in (
            HTTPStatus.OK,
            HTTPStatus.CREATED,
            HTTPStatus.NO_CONTENT,
        ):
            self.logger.info(
                "Registered webhook %s for project %s", self.remote_name, self.project
            )
            try:
                return response.json()
            except ValueError:
                return {}

        if response.status_code == HTTPStatus.CONFLICT or (
            response.status_code == HTTPStatus.BAD_REQUEST
            and "already exists" in response.text.lower()
        ):
            self.logger.info(
                "Webhook %s already exists for project %s",
                self.remote_name,
                self.project,
            )

            existing = self.session.get(url, headers={"Accept": "application/json"})
            existing.raise_for_status()
            return existing.json()

        response.raise_for_status()
