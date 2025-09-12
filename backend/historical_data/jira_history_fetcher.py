import json
from datetime import datetime
from typing import Any, cast
from jira.resources import Issue
from backend.common.logger import get_logger
from backend.common.redis_client import RedisClientFactory
from backend.common.jira_client import JiraClientFactory
from backend.common.constants import (
    JiraIssueStatus,
    JIRA_STATUS_ID_MAP,
    JIRA_EXCLUDED_STATUS_ID,
    JIRA_ISSUE_DETAILS_KEY,
    JIRA_LDAP_PROJECT_STATUS_INDEX_KEY,
    JIRA_MAX_RESULTS_DEFAULT,
    JIRA_STORY_POINT_FIELD,
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

    if JIRA_EXCLUDED_STATUS_ID == status_id:
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
    elif JiraIssueStatus.DONE == standard_status:
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

        if JiraIssueStatus.DONE == standard_status:
            finish_date = redis_data["finish_date"]
            pipeline.zadd(index_key, {issue_id: finish_date})

        else:
            pipeline.sadd(index_key, issue_id)

    pipeline.execute()

    return len(processed_issues)


def fetch_incremental_issues(hours: int, jira_client: Any) -> list[Any]:
    """
    Fetch all issues that were created or updated within the specified time window.

    Args:
        hours (int): Number of hours to look back
        jira_client (Any): Jira client instance

    Returns:
        list[Any]: List of Jira issue objects
    """
    if jira_client is None:
        raise ValueError("jira_client must not be None")

    jql_query = (
        f"(updated >= -{hours}h OR created >= -{hours}h) AND assignee IS NOT EMPTY"
    )
    issues = jira_client.search_issues(jql_query, maxResults=JIRA_MAX_RESULTS_DEFAULT)
    logger.info("Found %d changed issues in last %d hours", len(issues), hours)
    return issues


def group_incremental_issues_by_ldap(issues: list[Any]) -> dict[str, list[Any]]:
    """
    Group issues by ldap for batch processing in incremental operations.

    Args:
        issues (list[Any]): List of Jira issue objects

    Returns:
        dict[str, list[Any]]: Dictionary mapping ldap -> list of issues
    """
    grouped: dict[str, list[Any]] = {}
    for issue in issues:
        assignee = issue.fields.assignee
        if assignee and assignee.name:
            ldap = assignee.name
            if ldap not in grouped:
                grouped[ldap] = []
            grouped[ldap].append(issue)
    return grouped


def process_incremental_issues_data(
    ldap: str, user_issues: list[Any]
) -> list[dict[str, Any]]:
    """
    Process issue data for incremental operations.

    Args:
        ldap (str): User identifier
        user_issues (list[Any]): List of Jira issue objects for this user

    Returns:
        list[dict[str, Any]]: List of processed issue dictionaries ready for storage
    """
    valid_issues = []
    for issue in user_issues:
        typed_issue = cast(Issue, issue)
        processed = process_single_issue(typed_issue, ldap)
        if processed:
            valid_issues.append(processed)
    return valid_issues


def update_incremental_issue_indexes(
    processed_issues: list[dict[str, Any]], redis_client: Any
) -> tuple[int, int]:
    """
    Check which issues already exist in Redis and remove old indexes for incremental operations.

    Args:
        processed_issues (list[dict[str, Any]]): List of processed issue dictionaries
        redis_client (Any): Redis client instance

    Returns:
        tuple[int, int]: (created_count, updated_count)
    """
    if redis_client is None:
        raise ValueError("redis_client must not be None")

    pipe = redis_client.pipeline()
    created_count = 0
    updated_count = 0

    for processed_issue in processed_issues:
        issue_id = processed_issue["issue_id"]
        new_data = processed_issue["redis_data"]
        new_status = new_data["issue_status"]

        existing_key = JIRA_ISSUE_DETAILS_KEY.format(issue_id=issue_id)
        existing_data_response = redis_client.json().get(existing_key, "$")

        if existing_data_response and len(existing_data_response) > 0:
            # Issue exists - check if status changed before removing old indexes
            existing_data = existing_data_response[0]

            try:
                if isinstance(existing_data, str):
                    # Parse JSON string if Redis returned a string
                    existing_data = json.loads(existing_data)

                # Compare old and new status
                old_status = existing_data.get("issue_status")

                # Convert enum values to string for comparison if needed
                old_status_value = (
                    old_status.value if hasattr(old_status, "value") else old_status
                )
                new_status_value = (
                    new_status.value if hasattr(new_status, "value") else new_status
                )

                # Only remove old indexes if status actually changed
                if old_status_value != new_status_value:
                    remove_updated_issue_previous_indexes(issue_id, existing_data, pipe)
                    logger.debug(
                        "Status changed for issue %s: %s -> %s",
                        issue_id,
                        old_status_value,
                        new_status_value,
                    )
                else:
                    logger.debug(
                        "Status unchanged for issue %s: %s", issue_id, old_status_value
                    )

                updated_count += 1
            except (
                json.JSONDecodeError,
                TypeError,
                AttributeError,
                KeyError,
                IndexError,
            ) as e:
                logger.error(
                    "Error during updating incremental issue indexes processing issue %s: %s",
                    issue_id,
                    str(e),
                )
                raise
            except Exception as e:
                logger.error(
                    "Unexpected error during updating incremental issue indexes processing issue %s: %s",
                    issue_id,
                    str(e),
                )
                raise
        else:
            # New issue
            created_count += 1

    pipe.execute()
    return created_count, updated_count


def remove_updated_issue_previous_indexes(
    issue_id: str, existing_data: dict[str, Any], pipe: Any
) -> None:
    """
    Remove an issue from its current Redis indexes during incremental operations.

    Args:
        issue_id (str): Issue ID
        existing_data (dict[str, Any]): Current issue data from Redis
        pipe (Any): Redis pipeline instance
    """
    if pipe is None:
        raise ValueError("pipe must not be None")

    ldap = existing_data.get("ldap", "")
    project_id = existing_data.get("project_id", "")
    status = existing_data.get("issue_status", "")

    if not all([ldap, project_id, status]):
        logger.warning(
            "Missing index data for issue %s, skipping index removal", issue_id
        )
        return

    index_key = JIRA_LDAP_PROJECT_STATUS_INDEX_KEY.format(
        ldap=ldap,
        project_id=project_id,
        status=status.value if hasattr(status, "value") else status,
    )

    if status in (JiraIssueStatus.DONE, "done"):
        pipe.zrem(index_key, issue_id)
    else:
        pipe.srem(index_key, issue_id)


def process_update_jira_issues(hours: int) -> int:
    """
    Process Jira issues that were created or updated in the last N hours.
    This is an incremental update operation that handles both new and modified issues.

    Args:
        hours (int): Number of hours to look back for changed issues

    Returns:
        total_processed (int): Total number of issues processed
    """
    jira_client = JiraClientFactory().create_jira_client()
    redis_client = RedisClientFactory().create_redis_client()

    logger.info("Processing incremental Jira issues from last %d hours", hours)

    # 1. Get all changed issues (both created and updated)
    all_incremental_issues = fetch_incremental_issues(hours, jira_client)
    incremental_issues_by_ldap = group_incremental_issues_by_ldap(
        all_incremental_issues
    )

    # 2. Process each user's issues
    total_incremental = 0
    total_created = 0
    total_updated = 0

    for ldap, user_issues in incremental_issues_by_ldap.items():
        processed_incremental_issues = process_incremental_issues_data(
            ldap, user_issues
        )

        if processed_incremental_issues:
            # Check for updates and handle index cleanup
            created, updated = update_incremental_issue_indexes(
                processed_incremental_issues, redis_client
            )

            # Store all issues using existing method
            store_issues_in_redis(processed_incremental_issues, redis_client)

            total_created += created
            total_updated += updated
            total_incremental += len(processed_incremental_issues)

    logger.info(
        "Incremental update complete: total_incremental=%d, created=%d, updated=%d",
        total_incremental,
        total_created,
        total_updated,
    )

    return total_incremental
