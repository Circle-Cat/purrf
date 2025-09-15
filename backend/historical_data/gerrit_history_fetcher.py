import calendar
from datetime import datetime
from typing import Generator
from backend.common.logger import get_logger
from backend.common.redis_client import RedisClientFactory
from backend.common.gerrit_client import GerritClientFactory
from backend.common.constants import (
    GerritChangeStatus,
    ALL_GERRIT_STATUSES,
    GERRIT_UNDER_REVIEW,
    GERRIT_CL_REVIEWED_FIELD,
    GERRIT_UNDER_REVIEW_STATUS_VALUES,
    GERRIT_LOC_MERGED_FIELD,
    GERRIT_STATUS_TO_FIELD,
    GERRIT_DATE_BUCKET_TEMPLATE,
    GERRIT_STATS_ALL_TIME_KEY,
    GERRIT_STATS_MONTHLY_BUCKET_KEY,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GERRIT_DEDUPE_REVIEWED_KEY,
    GERRIT_CHANGE_STATUS_KEY,
)

logger = get_logger()


def fetch_changes(
    statuses: list[str] | None = None,
    projects: list[str] | None = None,
    max_changes: int | None = None,
    page_size: int = 500,
) -> Generator[dict, None, None]:
    """
    Generator that pages through Gerrit changes using the Gerrit REST API.
    Args:
        statuses (list[str] | None): Optional list of change statuses to filter by
            (e.g., ["merged", "abandoned", "open"]). If None, all statuses are considered.
        projects (list[str] | None): Optional list of project names to filter by. If None, all projects are considered.
        max_changes (int | None): Maximum number of changes to return. If None, fetches all matching changes.
        page_size (int): Number of results to fetch per API request. Defaults to 500.
    Yields:
        dict: A single change record returned from the Gerrit API.
    Example:
        list(fetch_changes(statuses=["merged", "abandoned"], projects=["purrf"], limit=1000, page_size=500))
        This translates to a query like:
        q=(status:merged OR status:abandoned) project:purrf&n=500&S=0
        (then continues pagination with S=500, S=1000, etc., until 1000 total changes are fetched)
    """
    client = GerritClientFactory().create_gerrit_client()
    total = 0
    start = 0
    queries: list[str] = []
    if statuses:
        status_clause = " OR ".join(f"status:{s}" for s in statuses)
    else:
        status_clause = None
    if not status_clause and not projects:
        queries = []
    elif status_clause and not projects:
        queries = [status_clause]
    elif projects and not status_clause:
        queries = [f"project:{p}" for p in projects]
    else:
        queries = [f"({status_clause}) project:{p}" for p in projects]
    while True:
        page = client.query_changes(
            queries=queries or [],
            limit=page_size,
            start=start,
            no_limit=False,
            options=[
                "CURRENT_REVISION",
                "DETAILED_LABELS",
                "DETAILED_ACCOUNTS",
                "MESSAGES",
            ],
            allow_incomplete=True,
        )
        if not page:
            break
        for change in page:
            if max_changes is not None and total >= max_changes:
                return
            yield change
            total += 1
        if max_changes is not None and total >= max_changes:
            break
        if len(page) < page_size:
            break
        start += page_size


def compute_buckets(created_str: str) -> str:
    """
    Compute monthly bucket key from Gerrit 'created' timestamp.
    Returns a string "YYYY-MM-DD_YYYY-MM-DD".
    """
    try:
        dt = datetime.strptime(created_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        dt = datetime.utcnow()
    year, month = dt.year, dt.month
    start = datetime(year, month, 1).date()
    last = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last).date()
    return GERRIT_DATE_BUCKET_TEMPLATE.format(start=start, end=end)


def store_change(change: dict) -> None:
    """
    Stores a single Gerrit change into Redis counters for analytics.
    Each user (owner or reviewer/commenter) ends up with these fields in:
      - gerrit:stats:{ldap}
      - gerrit:stats:{ldap}:{YYYY-MM-DD_YYYY-MM-DD}
      - gerrit:stats:{ldap}:{project}:{YYYY-MM-DD_YYYY-MM-DD}
    Fields per user:
      - cl_merged
      - cl_abandoned
      - loc_merged
      - cl_under_review
      - cl_reviewed
    Args:
        change (dict): A dictionary representing a Gerrit change with fields like owner, status, insertions, project, and created.
    Raises:
        ValueError: If the Redis client cannot be initialized.
    """
    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")
    ldap = change.get("owner", {}).get("username")
    state = change.get("status", "").lower()
    project = change.get("project")
    change_number = change.get("_number") or change.get("number")
    if "insertions" in change:
        insertions = change["insertions"]
    else:
        insertions = change.get("patchSet", {}).get("sizeInsertions", 0)
    if "created" in change:
        created_str = change["created"]
    else:
        ts = change.get("createdOn")
        created_str = (
            datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        )
    bucket = compute_buckets(created_str)
    new_tab = (
        GERRIT_UNDER_REVIEW if state in GERRIT_UNDER_REVIEW_STATUS_VALUES else state
    )
    new_cl_tab = GERRIT_STATUS_TO_FIELD.get(new_tab, f"cl_{new_tab}")
    logger.debug("ldap: %s", ldap)
    logger.debug("cl_%s", new_tab)
    logger.debug("bucket: %s", bucket)
    # all-time stats
    all_time_stats_key = GERRIT_STATS_ALL_TIME_KEY.format(ldap=ldap)
    # monthly bucket
    monthly_bucket_key = GERRIT_STATS_MONTHLY_BUCKET_KEY.format(
        ldap=ldap, bucket=bucket
    )
    # project-scoped bucket
    project_scoped_bucket_key = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
        ldap=ldap, project=project, bucket=bucket
    )
    pipe = redis_client.pipeline()
    review_dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=change_number)
    participants = {
        m["author"]["username"]
        for m in change.get("messages", [])
        if m.get("author", {}).get("username") and m["author"]["username"] != ldap
    }
    existing = redis_client.smembers(review_dedupe_key) or set()
    for user in participants - existing:
        bump_cl_reviewed(pipe, user, project, bucket)
    pipe.expire(review_dedupe_key, 60 * 60 * 24 * 90)
    pipe.execute()
    prev_tab = redis_client.hget(GERRIT_CHANGE_STATUS_KEY, change_number)
    if prev_tab == new_tab:
        logger.debug("CL %s already seen as %s; skipping", change_number, new_tab)
        return
    pipe = redis_client.pipeline()
    if prev_tab:
        old_field = GERRIT_STATUS_TO_FIELD.get(prev_tab, f"cl_{prev_tab}")
        pipe.hincrby(all_time_stats_key, old_field, -1)
        pipe.hincrby(monthly_bucket_key, old_field, -1)
        pipe.hincrby(project_scoped_bucket_key, old_field, -1)
    pipe.hincrby(all_time_stats_key, new_cl_tab, 1)
    pipe.hincrby(monthly_bucket_key, new_cl_tab, 1)
    pipe.hincrby(project_scoped_bucket_key, new_cl_tab, 1)
    if new_tab == GerritChangeStatus.MERGED.value:
        pipe.hincrby(all_time_stats_key, GERRIT_LOC_MERGED_FIELD, insertions)
        pipe.hincrby(monthly_bucket_key, GERRIT_LOC_MERGED_FIELD, insertions)
        pipe.hincrby(project_scoped_bucket_key, GERRIT_LOC_MERGED_FIELD, insertions)
    pipe.hset(GERRIT_CHANGE_STATUS_KEY, change_number, new_tab)
    pipe.execute()


def bump_cl_reviewed(pipe, user: str, project: str, bucket: str) -> None:
    """
    Add +1 to cl_reviewed for a given user across all‐time, monthly, and project scopes.
    """
    key_all = GERRIT_STATS_ALL_TIME_KEY.format(ldap=user)
    key_month = GERRIT_STATS_MONTHLY_BUCKET_KEY.format(ldap=user, bucket=bucket)
    key_proj = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
        ldap=user, project=project, bucket=bucket
    )
    for k in (key_all, key_month, key_proj):
        pipe.hincrby(k, GERRIT_CL_REVIEWED_FIELD, 1)


def fetch_and_store_changes(
    statuses: list[str] | None = None,
    projects: list[str] | None = None,
    max_changes: int | None = None,
    page_size: int = 500,
) -> None:
    """
    Orchestrator function that fetches Gerrit changes and stores them in Redis.
    Combines `fetch_changes` and `store_change`, logging progress and any errors encountered.
    Args:
        statuses (list[str] | None): Optional list of change statuses to filter by (e.g., ["merged", "abandoned", "open"]). If None, all statuses are included.
        projects (list[str] | None): Optional list of project names to filter by. If None, all projects are included.
        max_changes (int | None): Maximum number of changes to fetch and store. If None, all matching changes are processed.
        page_size (int): Number of results to fetch per API request to Gerrit. Defaults to 500.
    Raises:
        Exception: Propagates any exception encountered during processing after logging.
    """
    if not statuses:
        statuses = ALL_GERRIT_STATUSES
    total = 0
    try:
        for change in fetch_changes(statuses, projects, max_changes, page_size):
            store_change(change)
            total += 1
        logger.info("Finished processing %d Gerrit changes", total)
    except Exception as e:
        logger.error("Error after processing %d changes: %s", total, e)
        raise
