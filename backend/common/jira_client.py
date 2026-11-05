import os
import threading
from jira import JIRA
from backend.common.environment_constants import (
    JIRA_PASSWORD,
    TAILSCALE_PROXY,
)


class JiraClient:
    """
    A class for creating and managing a single, lazily-connected Jira client.

    Configuration and connectivity are checked at different times on purpose.
    Missing configuration is a broken deployment, so the constructor rejects it
    outright, using nothing but the environment. Reaching Jira is what waits:
    a rejected credential or an outage is something this process can neither
    tell apart from a transient failure nor fix by refusing to start, and the
    routes that never touch Jira should keep serving through it.

    The connection is opened by the first caller that asks for the client and
    reused from then on. A failed attempt is not remembered, so Jira coming
    back is enough -- no redeploy.
    """

    def __init__(
        self,
        jira_server: str,
        jira_user: str,
        logger,
        retry_utils,
    ):
        """
        Initializes the JiraClient without contacting Jira.

        Args:
            jira_server: The base URL of the Jira server.
            jira_user: The username or email for authentication.
            logger: A logger instance for logging operations.
            retry_utils: A utility for retrying transient connection errors.

        Raises:
            ValueError: If essential connection parameters are missing.
        """
        if not all([jira_server, jira_user]):
            raise ValueError("Jira server and user must be provided.")
        if not os.getenv(JIRA_PASSWORD):
            raise ValueError(
                f"Jira password not found in environment variable: {JIRA_PASSWORD}"
            )

        self._jira_server = jira_server.rstrip("/")
        self._jira_user = jira_user
        self.logger = logger
        self.retry_utils = retry_utils
        self._jira_client = None
        self._lock = threading.Lock()

    def _connect_to_jira(self) -> JIRA:
        """
        Create and return a connected Jira client using injected credentials.
        """
        jira_password = os.getenv(JIRA_PASSWORD)
        if not jira_password:
            raise ValueError(
                f"Jira password not found in environment variable: {JIRA_PASSWORD}"
            )

        proxy = os.getenv(TAILSCALE_PROXY)
        client = JIRA(
            server=self._jira_server,
            basic_auth=(self._jira_user, jira_password),
            proxies={"http": proxy, "https": proxy}
            if proxy
            else {"http": "", "https": ""},
        )
        client.server_info()
        self.logger.debug("[JiraClient] Jira connection verified successfully.")
        return client

    def get_jira_client(self) -> JIRA:
        """
        Provides the Jira client, connecting on the first call.

        Returns:
            JIRA: The connected Jira client.

        Raises:
            Exception: Whatever connecting raised, so the caller that needed
                Jira is the one that hears about it.
        """
        if self._jira_client is None:
            with self._lock:
                if self._jira_client is None:
                    try:
                        client = self.retry_utils.get_retry_on_transient(
                            self._connect_to_jira
                        )
                    except Exception as e:
                        self.logger.error(
                            "[JiraClient] Failed to create Jira client: %s", e
                        )
                        raise
                    self.logger.info("[JiraClient] Created Jira client successfully.")
                    self._jira_client = client
        return self._jira_client
