from backend.common.constants import JIRA_PROJECTS_KEY


class JiraAnalyticsService:
    def __init__(self, logger, redis_client, retry_utils):
        """
        Initialize the JiraAnalyticsService with necessary clients and logger.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.retry_utils = retry_utils

        if not logger:
            raise ValueError("Logger not provided.")
        if not self.redis_client:
            raise ValueError("Redis client not created.")
        if not self.retry_utils:
            raise ValueError("Retry utils not provided.")

    def get_all_jira_projects(self) -> dict[str, str]:
        """
        Retrieve all Jira project names stored in Redis hash 'jira:project'.

        Returns:
            dict[str, str]: Mapping of project_id (as str) to project_name
        """
        project_data = self.retry_utils.get_retry_on_transient(
            self.redis_client.hgetall, JIRA_PROJECTS_KEY
        )
        return project_data
