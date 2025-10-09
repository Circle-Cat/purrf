import os
from jira import JIRA
from backend.common.environment_constants import (
    JIRA_PASSWORD,
)


class JiraClient:
    """
    A class for creating and managing a single, eagerly-initialized Jira client.

    This class establishes and verifies the connection upon instantiation, ensuring
    that a valid client is immediately available for use via the get_client() method.
    """

    def __init__(
        self,
        jira_server: str,
        jira_user: str,
        logger,
        retry_utils,
    ):
        """
        Initializes the JiraClient and establishes the connection.

        Args:
            jira_server: The base URL of the Jira server.
            jira_user: The username or email for authentication.
            jira_password: The API token or password for authentication.
            logger: A logger instance for logging operations.
            retry_utils: A utility for retrying transient connection errors.

        Raises:
            ValueError: If essential connection parameters are missing.
        """
        if not all([jira_server, jira_user]):
            raise ValueError("Jira server and user must be provided.")

        self._jira_server = jira_server.rstrip("/")
        self._jira_user = jira_user
        self.logger = logger
        self.retry_utils = retry_utils

        try:
            jira_client = self.retry_utils.get_retry_on_transient(self._connect_to_jira)
            self.logger.info("Created Jira client successfully.")
            self._jira_client = jira_client
        except Exception as e:
            self.logger.error(f"Failed to create Jira client: {e}")
            raise

    def _connect_to_jira(self) -> JIRA:
        """
        Create and return a connected Jira client using injected credentials.
        """
        jira_password = os.getenv(JIRA_PASSWORD)
        if not jira_password:
            raise ValueError(
                f"Jira password not found in environment variable: {JIRA_PASSWORD}"
            )

        client = JIRA(
            server=self._jira_server,
            basic_auth=(self._jira_user, jira_password),
        )
        client.server_info()
        self.logger.debug("Jira connection verified successfully.")
        return client

    def get_jira_client(self) -> JIRA:
        """Provides public access to the initialized Jira client."""
        return self._jira_client
