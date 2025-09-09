from backend.common.constants import JIRA_PROJECTS_KEY


class JiraHistorySyncService:
    def __init__(self, logger, jira_client, redis_client):
        """
        Initialize JiraHistorySyncService.

        Args:
            logger: The logger instance for logging messages.
            jira_client: Jira client instance
            redis_client: Redis client instance
        """
        if logger is None:
            raise ValueError("logger must not be None")
        if jira_client is None:
            raise ValueError("jira_client must not be None")
        if redis_client is None:
            raise ValueError("redis_client must not be None")

        self.logger = logger
        self.jira_client = jira_client
        self.redis_client = redis_client

    def sync_jira_projects_id_and_name_mapping(self) -> int:
        """
        Fetch all Jira projects and store them in Redis as ID-to-name mapping.

        Returns:
            int: Total number of projects processed
        """
        projects = self.jira_client.projects()
        project_dict = {project.id: project.name for project in projects}

        if not project_dict:
            self.logger.error("No projects found in Jira")
            return 0

        self.logger.info("Fetched %d Jira projects", len(project_dict))

        self.redis_client.delete(JIRA_PROJECTS_KEY)
        self.logger.info("Cleared existing project data in Redis")

        self.redis_client.hset(JIRA_PROJECTS_KEY, mapping=project_dict)
        self.logger.info(
            "Successfully stored %d projects in Redis under key '%s'",
            len(project_dict),
            JIRA_PROJECTS_KEY,
        )

        self.logger.info("Jira projects ID-to-name sync completed successfully")

        return len(project_dict)
