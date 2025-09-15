import os
from http import HTTPStatus
from backend.common.environment_constants import (
    GERRIT_WEBHOOK_REMOTE_NAME,
    GERRIT_WEBHOOK_TARGET_URL,
    GERRIT_WEBHOOK_EVENTS,
    GERRIT_WEBHOOK_SECRET,
    GERRIT_WEBHOOK_PROJECT,
)


class GerritSubscriptionService:
    """
    Registers a webhook in Gerrit's Webhooks plugin.

    Uses the REST API:
    PUT /a/config/server/webhooks~projects/{project}/remotes/{remote}

    The webhook will send Gerrit events to the configured `GERRIT_WEBHOOK_TARGET_URL`.
    Handles "already exists" responses by retrieving the existing configuration.
    """

    def __init__(
        self, logger, gerrit_client, project: str = None, remote_name: str = None
    ):
        """
        Initializes the GerritWatcher with project and remote configuration.

        Args:
            logger: The logger instance for logging messages.
            gerrit_client: Gerrit client instance.
            project (str, optional): The Gerrit project to register the webhook for.
                Defaults to the value of GERRIT_WEBHOOK_PROJECT environment variable,
                or "All-Projects" if not set.
            remote_name (str, optional): The identifier for the webhook in Gerrit.
                Defaults to the value of GERRIT_WEBHOOK_REMOTE_NAME environment variable,
                or "gerrit-webhook" if not set.

        Raises:
            RuntimeError: If GERRIT_WEBHOOK_TARGET_URL is not set in the environment.
        """
        if gerrit_client is None:
            raise ValueError("gerrit_client must not be None")

        self.logger = logger
        self.gerrit_client = gerrit_client
        self.base_url = self.gerrit_client.base_url.rstrip("/")
        self.session = self.gerrit_client.session

        self.project = project or os.getenv(GERRIT_WEBHOOK_PROJECT, "All-Projects")
        self.remote_name = remote_name or os.getenv(
            GERRIT_WEBHOOK_REMOTE_NAME, "gerrit-webhook"
        )

        self.subscribe_url = os.getenv(GERRIT_WEBHOOK_TARGET_URL)
        if not self.subscribe_url:
            raise RuntimeError("GERRIT_WEBHOOK_TARGET_URL must be set")

        self.secret = os.getenv(GERRIT_WEBHOOK_SECRET, None)
        self.events = os.getenv(
            GERRIT_WEBHOOK_EVENTS,
            "patchset-created,change-merged,change-abandoned,comment-added,change-restored",
        ).split(",")
        logger.debug(
            f"[GerritWatcher] Subscribing to events: {self.events} "
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

        if self.secret:
            payload["secret"] = self.secret

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
