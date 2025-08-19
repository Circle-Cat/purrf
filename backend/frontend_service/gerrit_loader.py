from backend.common.logger import get_logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from backend.common.redis_client import RedisClientFactory
from backend.frontend_service.ldap_loader import get_all_active_ldap_users
import re
from datetime import date, datetime, timedelta
from backend.common.constants import (
    GERRIT_DATE_BUCKET_TEMPLATE,
    GERRIT_STAT_FIELDS,
    GERRIT_STATS_ALL_TIME_KEY,
    GERRIT_STATS_MONTHLY_BUCKET_KEY,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
)

logger = get_logger()


def parse_date(date_str: str | None) -> date | None:
    """
    Parse an ISO‐style date string into a `date` object.

    Args:
        date_str: A string in "YYYY-MM-DD" format, or None/empty.

    Returns:
        A `date` object corresponding to `date_str`, or None if `date_str` is None or empty.

    Raises:
        ValueError: If `date_str` is non‐empty but not in valid "YYYY-MM-DD" format.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format")


def get_month_buckets(start: date, end: date) -> list[str]:
    """Returns a list of calendar month bucket strings like 'YYYY-MM-DD_YYYY-MM-DD'."""
    if start > end:
        raise ValueError(f"start_date ({start}) must be <= end_date ({end})")
    buckets = []
    current = date(start.year, start.month, 1)
    while current <= end:
        last_day = (current.replace(day=28) + timedelta(days=4)).replace(
            day=1
        ) - timedelta(days=1)
        bucket = GERRIT_DATE_BUCKET_TEMPLATE.format(
            start=current.isoformat(), end=last_day.isoformat()
        )
        buckets.append(bucket)
        current = (last_day + timedelta(days=1)).replace(day=1)
    return buckets


LDAP_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_gerrit_stats(
    raw_ldap: str | None = None,
    start_date_str: str | None = None,
    end_date_str: str | None = None,
    raw_project: str | None = None,
) -> dict[str, dict]:
    """
    Aggregate Gerrit stats from Redis buckets.

    Args:
        ldap_list: List of LDAP usernames to include.
        start_date: Beginning of date range (inclusive).
        end_date: End of date range (inclusive).
        project_list: Optional project name filter.

    Returns:
        Dictionary keyed by LDAP, each containing aggregated stat fields.
    """
    ldap_list = [s.strip() for s in (raw_ldap or "").split(",") if s.strip()]
    if not ldap_list:
        ldap_list = get_all_active_ldap_users()
        if not ldap_list:
            logger.warning("No active LDAP users found.")
            return {}
        logger.debug("Loaded all LDAPs: %s", ldap_list)

    invalid = [ldap for ldap in ldap_list if not LDAP_RE.fullmatch(ldap)]
    if invalid:
        raise ValueError(f"Invalid LDAP(s): {invalid}")

    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")

    start_date = parse_date(start_date_str)
    end_date = parse_date(end_date_str)
    use_month_buckets = start_date is not None and end_date is not None
    month_buckets = get_month_buckets(start_date, end_date) if use_month_buckets else []

    project_list = raw_project.split(",") if raw_project else None
    projects = [p for p in (project_list or []) if p] or [None]

    pipeline = redis_client.pipeline()
    gerrit_stats_count_map = {}

    for ldap in ldap_list:
        if use_month_buckets:
            for bucket in month_buckets:
                for proj in projects:
                    key = (
                        GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                            ldap=ldap, project=proj, bucket=bucket
                        )
                        if proj
                        else GERRIT_STATS_MONTHLY_BUCKET_KEY.format(
                            ldap=ldap, bucket=bucket
                        )
                    )
                    pipeline.hgetall(key)
                    gerrit_stats_count_map[key] = (ldap, proj, bucket)
        else:
            key = GERRIT_STATS_ALL_TIME_KEY.format(ldap=ldap)
            pipeline.hgetall(key)
            gerrit_stats_count_map[key] = (ldap, None, None)

    results = pipeline.execute()

    stats = {ldap: {f: 0 for f in GERRIT_STAT_FIELDS} for ldap in ldap_list}

    for (key, (ldap, _, _)), data in zip(gerrit_stats_count_map.items(), results):
        for field in GERRIT_STAT_FIELDS:
            if field in data:
                stats[ldap][field] += int(data[field])

    return stats
