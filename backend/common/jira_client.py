import os
from jira import JIRA
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.common.logger import get_logger
from backend.common.environment_constants import (
    JIRA_SERVER,
    JIRA_USER,
    JIRA_PASSWORD,
)

logger = get_logger()


class JiraClientFactory:
    """
    A singleton factory class for creating and managing Jira client.

    This class ensures that only one Jira client instance is created and shared
    across the application. It handles credential management and client creation
    with automatic retries on transient failures.

    Attributes:
        _instance (JiraClientFactory): The singleton instance of the factory.
        _client (JIRA): The created Jira client instance.
        _credentials (dict[str, str]): The cached Jira credentials.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize attributes only once."""
        if not hasattr(self, "_initialized"):
            self._client = None
            self._credentials = None
            self._initialized = True

    def _get_credentials(self) -> dict[str, str]:
        """Load and cache Jira credentials."""
        if self._credentials is None:
            server = os.getenv(JIRA_SERVER)
            user = os.getenv(JIRA_USER)
            password = os.getenv(JIRA_PASSWORD)

            if not all([server, user, password]):
                missing = [
                    name
                    for name, val in [
                        (JIRA_SERVER, server),
                        (JIRA_USER, user),
                        (JIRA_PASSWORD, password),
                    ]
                    if not val
                ]
                raise ValueError(f"Missing Jira credentials: {', '.join(missing)}")

            self._credentials = {
                "server": server.rstrip("/"),
                "username": user,
                "password": password,
            }
            logger.info("Jira credentials loaded")
        return self._credentials

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=3),
    )
    def create_jira_client(self) -> JIRA:
        """Create and return a Jira client instance."""
        if self._client is None:
            creds = self._get_credentials()
            logger.info("Creating Jira client instance")
            self._client = JIRA(
                server=creds["server"],
                basic_auth=(creds["username"], creds["password"]),
            )
        return self._client
