from typing import Any
from src.common.logger import get_logger
from src.common.redis_client import RedisClientFactory
from src.common.jira_client import JiraClientFactory
from src.common.constants import JIRA_PROJECTS_KEY


logger = get_logger()


def fetch_jira_projects(jira_client: Any) -> dict[str, str]:
    """
    Fetch all Jira projects and return as ID to name mapping.

    Args:
        jira_client: Jira client instance

    Returns:
        Dict mapping project IDs to project names

    Raises:
        ValueError: If jira_client is None
    """
    if jira_client is None:
        raise ValueError("jira_client must not be None")

    logger.info("Fetching all Jira projects")

    projects = jira_client.projects()
    project_dict = {project.id: project.name for project in projects}

    logger.info("Successfully fetched %d projects", len(project_dict))

    return project_dict


def store_jira_projects_in_redis(
    project_dict: dict[str, str], redis_client: Any
) -> int:
    """
    Store project ID to name mappings in Redis hash.

    Args:
        project_dict: Dictionary mapping project IDs to names
        redis_client: Redis client instance

    Returns:
        Number of projects stored

    Raises:
        ValueError: If redis_client is None
    """
    if redis_client is None:
        raise ValueError("redis_client must not be None")

    if not project_dict:
        logger.warning("No projects to store in Redis")
        return 0

    # Full overwrite: delete the existing hash before creating a new one
    redis_client.delete(JIRA_PROJECTS_KEY)
    logger.info("Cleared existing project data in Redis")

    # Store the project mapping
    redis_client.hset(JIRA_PROJECTS_KEY, mapping=project_dict)

    stored_count = len(project_dict)
    logger.info(
        "Successfully overwrote %d projects in Redis hash '%s'",
        stored_count,
        JIRA_PROJECTS_KEY,
    )

    return stored_count


def process_sync_jira_projects() -> int:
    """
    Process Jira projects and store them in Redis.

    Returns:
        int: Total number of projects processed
    """
    jira_client = JiraClientFactory().create_jira_client()
    redis_client = RedisClientFactory().create_redis_client()

    logger.info("Starting Jira projects synchronization")

    project_dict = fetch_jira_projects(jira_client)

    if not project_dict:
        logger.error("No projects found in Jira")
        raise RuntimeError("No projects found in Jira")

    total_projects = store_jira_projects_in_redis(project_dict, redis_client)

    logger.info(
        "Jira projects synchronization completed. Processed %d projects", total_projects
    )

    return total_projects
