from redis import Redis
from backend.common.logger import get_logger
from backend.common.redis_client import RedisClientFactory
from backend.common.constants import (
    JIRA_PROJECTS_KEY,
    JIRA_ISSUE_DETAILS_KEY,
)

logger = get_logger()


def _validate_issue_ids(issue_ids):
    """Validate and convert issue IDs to integers."""
    if not issue_ids:
        raise ValueError("issue_ids is required")

    if not isinstance(issue_ids, list):
        raise ValueError("issue_ids must be a list")

    try:
        validated_issue_ids = [int(issue_id) for issue_id in issue_ids]
    except (ValueError, TypeError) as e:
        raise ValueError(f"All issue_ids must be valid integers: {e}") from e

    return validated_issue_ids


def _fetch_issue_details_and_project_names(validated_issue_ids):
    """Fetch issue details and project names from Redis."""
    redis_client: Redis = RedisClientFactory().create_redis_client()

    # Step 1: Batch fetch issues using pipeline
    pipeline = redis_client.pipeline()
    for issue_id in validated_issue_ids:
        redis_key = JIRA_ISSUE_DETAILS_KEY.format(issue_id=issue_id)
        pipeline.json().get(redis_key, "$")

    try:
        pipeline_results = pipeline.execute()
    except Exception as e:
        logger.error(f"Redis pipeline execution failed: {e}")
        raise

    # Step 2: Process issue results and collect project IDs
    project_ids_to_fetch = set()
    issue_details = {}

    for i, issue_id in enumerate(validated_issue_ids):
        issue_data_json = pipeline_results[i]
        try:
            if issue_data_json:
                # RedisJSON returns a list, get the first element
                if isinstance(issue_data_json, list) and len(issue_data_json) > 0:
                    issue_data = issue_data_json[0]
                else:
                    issue_data = issue_data_json
                issue_details[issue_id] = issue_data
                if isinstance(issue_data, dict):
                    project_id = issue_data.get("project_id")
                    if project_id:
                        project_ids_to_fetch.add(str(project_id))
            else:
                # Issue not found in Redis
                logger.warning(f"Issue {issue_id} not found in Redis")
                issue_details[issue_id] = None
        except Exception as e:
            logger.error(f"Failed to process issue {issue_id}: {e}")
            raise

    # Step 3: Batch fetch project names
    project_names = {}
    if project_ids_to_fetch:
        try:
            project_ids_to_fetch_list = list(project_ids_to_fetch)
            project_names_values = redis_client.hmget(
                JIRA_PROJECTS_KEY, project_ids_to_fetch_list
            )
            for i, project_id in enumerate(project_ids_to_fetch_list):
                project_name = project_names_values[i]
                if project_name:
                    project_names[project_id] = project_name
                else:
                    logger.warning(
                        f"Project name not found for project_id: {project_id}"
                    )
                    project_names[project_id] = None
        except Exception as e:
            logger.error(f"Failed to fetch project names: {e}")
            raise

    return issue_details, project_names


def _build_final_result(validated_issue_ids, issue_details, project_names):
    """Build the final result dictionary with all 8 fields."""
    result = {}

    for issue_id in validated_issue_ids:
        issue_data = issue_details.get(issue_id)
        if issue_data:
            project_id = issue_data.get("project_id")
            project_id_int = int(project_id) if project_id is not None else None
            project_name = project_names.get(str(project_id)) if project_id else None
            # Construct the 8-field result
            result[str(issue_id)] = {
                "ldap": issue_data.get("ldap"),
                "finish_date": issue_data.get("finish_date"),
                "issue_key": issue_data.get("issue_key"),
                "story_point": issue_data.get("story_point"),
                "project_id": project_id_int,
                "project_name": project_name,
                "issue_status": issue_data.get("issue_status"),
                "issue_title": issue_data.get("issue_title"),
            }
        else:
            logger.warning(f"issue_data is None for issue_id: {issue_id}")
            result[str(issue_id)] = None

    return result


def process_get_issue_detail_batch(issue_ids) -> dict[str, dict]:
    """
    Get Jira issue details in batch from Redis.

    Redis keys are structured as JIRA_ISSUE_DETAILS_KEY, and this function
    fetches a list of issue details by issue id.

    Args:
        issue_ids: Issue IDs from request (can be None, list, or any type)

    Returns:
        Dictionary mapping issue_id (str) to issue details (dict)

    Raises:
        ValueError: If request body is invalid or issue_ids is missing/invalid
        Exception: If Redis operations fail
    """
    # Step 1: Validate input
    validated_issue_ids = _validate_issue_ids(issue_ids)

    # Step 2: Fetch issues and project names from Redis
    issue_details, project_names = _fetch_issue_details_and_project_names(
        validated_issue_ids
    )

    # Step 3: Build final result
    result = _build_final_result(validated_issue_ids, issue_details, project_names)

    return result
