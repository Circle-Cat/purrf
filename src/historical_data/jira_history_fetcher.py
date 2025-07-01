from datetime import datetime
from typing import Any, cast
from jira.resources import Issue
from src.common.logger import get_logger
from src.common.redis_client import RedisClientFactory
from src.common.jira_client import JiraClientFactory
from src.frontend_service.ldap_loader import get_all_ldaps_and_displaynames
from src.common.constants import (
    JiraIssueStatus,
    JIRA_STATUS_ID_MAP,
    JIRA_EXCLUDED_STATUS_ID,
    JIRA_ISSUE_DETAILS_KEY,
    JIRA_LDAP_PROJECT_STATUS_INDEX_KEY,
    JIRA_MAX_RESULTS_DEFAULT,
    JIRA_PROJECTS_KEY,
    JIRA_STORY_POINT_FIELD,
    MicrosoftAccountStatus,
)


logger = get_logger()


def format_resolution_date(date_str: str | None) -> int | None:
    """
    Convert a Jira datetime string (e.g. '2023-07-12T14:35:22.123+0000')
    to an integer YYYYMMDD format.

    Args:
        date_str: Date string in format "YYYY-MM-DDTHH:MM:SS.mmm±HHMM", or None.

    Returns:
        Integer representation of the date in YYYYMMDD format,
        or None if the input is invalid or cannot be parsed.
    """
    if not isinstance(date_str, str) or not date_str.strip():
        logger.warning("Invalid date input: %s", date_str)
        return None

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        return int(dt.strftime("%Y%m%d"))
    except ValueError as e:
        logger.warning("Date format error: %s — %s", date_str, e)
        return None


def process_single_issue(issue: Issue, ldap: str) -> dict[str, Any] | None:
    """
    Process one Jira issue and extract key fields for Redis storage.

    Args:
        issue (Issue): Jira issue object.
        ldap (str): User's LDAP ID.

    Returns:
        dict[str, Any] | None: A dictionary with issue info, or None if the issue is invalid,
        has an excluded status, or unknown status ID.
    """
    issue_raw_data = issue.raw
    if issue_raw_data is None:
        return None

    fields = issue_raw_data.get("fields", {})
    issue_title = fields.get("summary", "")
    project_info = fields.get("project", {})
    project_id = project_info.get("id", "") if isinstance(project_info, dict) else ""
    story_point = fields.get(JIRA_STORY_POINT_FIELD)
    status_info = fields.get("status", {})
    status_id = status_info.get("id", "") if status_info else ""

    if status_id == JIRA_EXCLUDED_STATUS_ID:
        return None

    standard_status = JIRA_STATUS_ID_MAP.get(status_id) if status_id else None
    if not standard_status:
        logger.warning(
            "Unknown status ID '%s' for issue %s", status_id, issue_raw_data.get("key")
        )
        return None

    finish_date = None
    resolution_date = fields.get("resolutiondate")
    if resolution_date:
        finish_date = format_resolution_date(resolution_date)
    elif standard_status == JiraIssueStatus.DONE:
        for date_field in ["updated", "created"]:
            date_value = fields.get(date_field)
            if date_value:
                finish_date = format_resolution_date(date_value)
                logger.warning(
                    "Issue %s has DONE status but no resolutiondate, using %s instead",
                    issue_raw_data.get("key"),
                    date_field,
                )
                break

    return {
        "issue_id": issue_raw_data.get("id"),
        "redis_data": {
            "issue_key": issue_raw_data.get("key"),
            "issue_title": issue_title,
            "project_id": project_id,
            "story_point": story_point,
            "issue_status": standard_status,
            "ldap": ldap,
            "finish_date": finish_date,
        },
    }


def fetch_issues_with_metadata(ldap: str, jira_client: Any) -> dict[str, Any]:
    """
    Fetch Jira issues assigned to a specific user and process them for storage.

    This method handles the complete data processing pipeline:
    - Fetching raw data from Jira API
    - Extracting and transforming fields
    - Mapping status IDs to standard statuses
    - Formatting dates
    - Building storage-ready data structures

    Args:
        ldap (str): The user identifier (LDAP username) to search for
            assigned issues
        jira_client (Any): Jira client instance

    Returns:
        dict[str, Any]: Dictionary containing:
            - valid_issues (list): List of processed issue dictionaries ready
                for storage
            - fetched_issues_count (int): Total number of issues found
            - excluded_issues_count (int): Number of issues explicitly excluded by
                status
            - failed_to_parse_issues_count (int): Number of issues with unknown/
                unmappable status
    """
    if jira_client is None:
        raise ValueError("jira_client must not be None")

    jql_query = f'assignee = "{ldap}"'
    issues = jira_client.search_issues(jql_query, maxResults=JIRA_MAX_RESULTS_DEFAULT)

    logger.info("Found %d issues assigned to %s", len(issues), ldap)

    fetched_issues_count = len(issues)
    excluded_issues_count = 0
    failed_to_parse_issues_count = 0
    valid_issues = []

    for issue in issues:
        typed_issue = cast(Issue, issue)
        result = process_single_issue(typed_issue, ldap)

        if result:
            valid_issues.append(result)
        else:
            issue_raw_data = typed_issue.raw or {}
            status_id = issue_raw_data.get("fields", {}).get("status", {}).get("id")
            if status_id == JIRA_EXCLUDED_STATUS_ID:
                excluded_issues_count += 1
            else:
                failed_to_parse_issues_count += 1

    return {
        "valid_issues": valid_issues,
        "fetched_issues_count": fetched_issues_count,
        "excluded_issues_count": excluded_issues_count,
        "failed_to_parse_issues_count": failed_to_parse_issues_count,
    }


def store_issues_in_redis(
    processed_issues: list[dict[str, Any]], redis_client: Any
) -> int:
    """
    Add processed Jira issues to Redis pipeline for batch storage.

    Args:
        processed_issues (list[dict[str, Any]]): List of pre-processed issue data ready
            for storage
        redis_client (Any): Redis client instance to create the pipeline

    Returns:
        int: Number of issues added to pipeline and executed

    Raises:
        Exception: Any pipeline operation errors propagate to caller
    """
    if redis_client is None:
        raise ValueError("redis_client must not be None")
    if not processed_issues:
        return 0

    pipeline = redis_client.pipeline()

    for processed_issue in processed_issues:
        issue_id = processed_issue["issue_id"]
        redis_data = processed_issue["redis_data"]
        ldap = redis_data["ldap"]
        standard_status = redis_data["issue_status"]

        # Add main issue data storage to pipeline
        redis_key = JIRA_ISSUE_DETAILS_KEY.format(issue_id=issue_id)
        pipeline.json().set(redis_key, "$", redis_data)

        # Add index operations to pipeline
        index_key = JIRA_LDAP_PROJECT_STATUS_INDEX_KEY.format(
            ldap=ldap,
            project_id=redis_data["project_id"],
            status=(
                standard_status.value
                if isinstance(standard_status, JiraIssueStatus)
                else standard_status
            ),
        )

        if standard_status == JiraIssueStatus.DONE:
            finish_date = redis_data["finish_date"]
            pipeline.zadd(index_key, {issue_id: finish_date})

        else:
            pipeline.sadd(index_key, issue_id)

    pipeline.execute()

    return len(processed_issues)


def fetch_and_store_issues_for_ldap(
    ldap: str, jira_client: Any, redis_client: Any
) -> dict[str, Any]:
    """
    Fetch and store all Jira issues for a specific user.

    This is the main orchestration method that coordinates fetching and
    storing.

    Args:
        ldap (str): The user identifier (LDAP username) to process
        jira_client (Any): Jira client instance
        redis_client (Any): Redis client instance

    Returns:
        dict[str, Any]: Dictionary containing processing statistics:
            - ldap (str): The processed user identifier
            - fetched_issues_count (int): Number of issues fetched from Jira
            - excluded_issues_count (int): Number of issues excluded by status
            - failed_to_parse_issues_count (int): Number of issues with unknown
                status
            - stored_issues_count (int): Number of issues successfully stored
            - failed_to_store_issues_count (int): Number of issues failed to store
    """

    if jira_client is None:
        raise ValueError("jira_client must not be None")
    if redis_client is None:
        raise ValueError("redis_client must not be None")

    stored_issues_count = 0
    failed_to_store_issues_count = 0

    # Fetch and process all issues for the user
    result = fetch_issues_with_metadata(ldap, jira_client)
    # Already processed and ready for storage
    processed_issues = result["valid_issues"]
    fetched_issues_count = result["fetched_issues_count"]
    excluded_issues_count = result["excluded_issues_count"]
    failed_to_parse_issues_count = result["failed_to_parse_issues_count"]

    if processed_issues:
        stored_issues_count = store_issues_in_redis(processed_issues, redis_client)
        failed_to_store_issues_count = 0

    logger.info(
        "%s: fetched=%d, excluded=%d, failed_to_parse=%d, stored=%d, "
        "failed_to_store=%d",
        ldap,
        fetched_issues_count,
        excluded_issues_count,
        failed_to_parse_issues_count,
        stored_issues_count,
        failed_to_store_issues_count,
    )

    return {
        "ldap": ldap,
        "fetched_issues_count": int(fetched_issues_count),
        "excluded_issues_count": int(excluded_issues_count),
        "failed_to_parse_issues_count": int(failed_to_parse_issues_count),
        "stored_issues_count": int(stored_issues_count),
        "failed_to_store_issues_count": int(failed_to_store_issues_count),
    }


def process_backfill_jira_issues() -> int:
    """
    Process Jira backfill for all users in the system.

    This method orchestrates the complete backfill process:
    - Retrieves all user LDAPs
    - Processes each user sequentially
    - Provides comprehensive logging and statistics

    Returns:
        int: Total issues successfully stored across all users
    """
    logger.info("Starting Jira backfill for all ldaps")

    # Get all user LDAPs from directory
    all_ldaps: dict[str, str] = get_all_ldaps_and_displaynames(
        MicrosoftAccountStatus.ALL
    )
    ldaps = list(all_ldaps.keys())
    logger.info("Found %d ldaps to process", len(ldaps))

    if not ldaps:
        logger.warning("No ldaps found in directory")
        raise RuntimeError("No ldaps found in directory")

    # Initialize clients
    jira_client = JiraClientFactory().create_jira_client()
    redis_client = RedisClientFactory().create_redis_client()

    # Initialize counters
    total_stored_issues_count = 0
    total_fetched_issues_count = 0
    total_excluded_issues_count = 0
    total_failed_issues_count = 0
    processed_ldaps_count = 0

    # Process each user
    for i, ldap in enumerate(ldaps, 1):
        logger.info("Processing ldap %d/%d: %s", i, len(ldaps), ldap)

        try:
            result = fetch_and_store_issues_for_ldap(ldap, jira_client, redis_client)
            total_stored_issues_count += int(result.get("stored_issues_count", 0))
            total_fetched_issues_count += int(result.get("fetched_issues_count", 0))
            total_excluded_issues_count += int(result.get("excluded_issues_count", 0))
            failed_parse_count = int(result.get("failed_to_parse_issues_count", 0))
            failed_store_count = int(result.get("failed_to_store_issues_count", 0))
            total_failed_issues_count += failed_parse_count + failed_store_count
            processed_ldaps_count += 1
        except Exception as e:
            logger.error("Failed to process ldap %s: %s", ldap, e)
            raise

    # Log final summary
    logger.info(
        "Summary:\n"
        "  ldaps:   fetched=%d, processed=%d\n"
        "  issues:  fetched=%d, stored=%d, excluded=%d, failed=%d",
        len(ldaps),
        processed_ldaps_count,
        total_fetched_issues_count,
        total_stored_issues_count,
        total_excluded_issues_count,
        total_failed_issues_count,
    )

    return total_stored_issues_count


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
