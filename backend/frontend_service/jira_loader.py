from redis import Redis
from backend.common.logger import get_logger
from backend.common.redis_client import RedisClientFactory
from backend.common.constants import (
    JIRA_LDAP_PROJECT_STATUS_INDEX_KEY,
    JiraIssueStatus,
    JIRA_PROJECTS_KEY,
    JIRA_ISSUE_DETAILS_KEY,
)
from backend.utils.date_time_util import get_start_end_timestamps

logger = get_logger()


# TODO: [PUR-134] Move datetime-related methods in Jira module into a utility class
def _convert_datetime_to_score(dt) -> int:
    """
    Convert datetime to YYYYMMDD integer for Redis scoring.

    Args:
        dt: datetime object

    Returns:
        Integer in YYYYMMDD format
    """
    return int(dt.strftime("%Y%m%d"))


def get_issue_ids_in_timerange(
    status: str,
    ldaps: list[str] | None = None,
    project_ids: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, dict[str, dict[str, list[int]]]]:
    """
    Process the request to get issue IDs from Redis.

    Args:
        status (str): The Jira issue status ("done", "in_progress", "todo", "all").
        ldaps (list[str] or None): List of LDAP identifiers to filter by. Required.
        project_ids (list[str] or None): List of project IDs to filter by. Required.
        start_date (str or None): Start date in "YYYY-MM-DD" format. Required for "done" or "all".
        end_date (str or None): End date in "YYYY-MM-DD" format. Required for "done" or "all".

    Returns:
        dict: Issue IDs grouped by status, ldap and project:
            {
                "<status>": {
                    "<ldap>": {
                        "<project_id>": ["<issue_id>", ...],
                    },
                },
            }

    Raises:
        ValueError: If required parameters are missing or invalid.
    """

    try:
        validated_status = JiraIssueStatus(status)
    except ValueError as e:
        raise ValueError(f"Invalid status: {status}") from e

    if not ldaps:
        raise ValueError("ldaps is required")

    if not project_ids:
        raise ValueError("project_ids is required")

    if validated_status in (JiraIssueStatus.DONE, JiraIssueStatus.ALL):
        start_dt, end_dt = get_start_end_timestamps(start_date, end_date)
        start_date_score = _convert_datetime_to_score(start_dt)
        end_date_score = _convert_datetime_to_score(end_dt)
    else:
        start_date_score = end_date_score = None

    logger.info(
        f"Processing get issue IDs request: status={status}, ldaps={ldaps}, "
        f"project_ids={project_ids}, start_date_score={start_date_score}, end_date_score={end_date_score}"
    )

    redis_client = RedisClientFactory().create_redis_client()

    if validated_status == JiraIssueStatus.ALL:
        result = {}
        for single_status in [
            JiraIssueStatus.TODO,
            JiraIssueStatus.IN_PROGRESS,
            JiraIssueStatus.DONE,
        ]:
            result[single_status.value] = _get_issues_for_status(
                redis_client,
                single_status,
                ldaps,
                project_ids,
                start_date_score,
                end_date_score,
            )
        return result

    return {
        validated_status.value: _get_issues_for_status(
            redis_client,
            validated_status,
            ldaps,
            project_ids,
            start_date_score,
            end_date_score,
        )
    }


def _get_issues_for_status(
    redis_client,
    status: JiraIssueStatus,
    ldaps: list[str],
    project_ids: list[str],
    start_date_score: int | None = None,
    end_date_score: int | None = None,
) -> dict[str, dict[str, list[int]]]:
    """
    Get issue IDs for a specific status from Redis using pipeline for better performance.
    """
    pipeline = redis_client.pipeline()
    result_key_pairs = []  # [(ldap, project_id), ...]
    for ldap in ldaps:
        for project_id in project_ids:
            redis_key = JIRA_LDAP_PROJECT_STATUS_INDEX_KEY.format(
                ldap=ldap, project_id=project_id, status=status.value
            )
            result_key_pairs.append((ldap, project_id))
            if status == JiraIssueStatus.DONE and start_date_score and end_date_score:
                pipeline.zrangebyscore(redis_key, start_date_score, end_date_score)
            else:
                pipeline.smembers(redis_key)
    try:
        pipeline_results = pipeline.execute()
    except Exception as e:
        logger.error(f"Redis pipeline execution failed: {e}")
        raise
    result = {ldap: {} for ldap in ldaps}
    for i, (ldap, project_id) in enumerate(result_key_pairs):
        issue_ids = pipeline_results[i]
        try:
            if issue_ids:
                result[ldap][project_id] = [int(issue_id) for issue_id in issue_ids]
            else:
                result[ldap][project_id] = []
        except Exception as e:
            logger.warning(f"Failed to process results for {ldap}/{project_id}: {e}")
            raise
    return result


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
