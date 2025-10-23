import re
from datetime import date, timedelta
from backend.common.constants import (
    GERRIT_DATE_BUCKET_TEMPLATE,
    GERRIT_STAT_FIELDS,
    GERRIT_STATS_ALL_TIME_KEY,
    GERRIT_STATS_BUCKET_KEY,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GERRIT_PROJECTS_KEY,
)


class GerritAnalyticsService:
    def __init__(self, logger, redis_client, retry_utils, ldap_service, date_time_util):
        """
        Gerrit Analytics Service to aggregate stats from Redis.

        Args:
            logger: Logger instance.
            redis_client: The Redis client instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
            ldap_service: Service that can provide active LDAP users.
            date_time_util: A DateTimeUtil instance for handling date and time operations.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.retry_utils = retry_utils
        self.ldap_service = ldap_service
        self.date_time_util = date_time_util
        self.LDAP_RE = re.compile(r"^[A-Za-z0-9_-]+$")

    def get_gerrit_projects(self) -> list[str]:
        """
        Retrieve all Gerrit project names stored in Redis set 'gerrit:projects'.

        Returns:
            list[str]: A list of project names.
        """
        projects = self.retry_utils.get_retry_on_transient(
            self.redis_client.smembers, GERRIT_PROJECTS_KEY
        )
        return sorted(list(projects))

    def _get_month_buckets(self, start: date, end: date) -> list[str]:
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

    def get_gerrit_stats(
        self,
        ldap_list: list[str] | None = None,
        start_date_str: str | None = None,
        end_date_str: str | None = None,
        project_list: list[str] | None = None,
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
        if not ldap_list:
            ldap_list = self.ldap_service.get_all_active_interns_and_employees_ldaps()
            if not ldap_list:
                self.logger.warning("No active LDAP users found.")
                return {}
            self.logger.info(
                "Fetched all active interns and employees LDAP count: %d",
                len(ldap_list),
            )

        invalid = [ldap for ldap in ldap_list if not self.LDAP_RE.fullmatch(ldap)]
        if invalid:
            raise ValueError(f"Invalid LDAP(s): {invalid}")

        if start_date_str is not None and end_date_str is not None:
            start_date, end_date = self.date_time_util.get_start_end_timestamps(
                start_date_str, end_date_str
            )
            start_date, end_date = start_date.date(), end_date.date()
        else:
            start_date, end_date = None, None

        use_month_buckets = start_date is not None and end_date is not None
        month_buckets = (
            self._get_month_buckets(start_date, end_date) if use_month_buckets else []
        )

        projects = [p for p in (project_list or []) if p] or [None]

        pipeline = self.redis_client.pipeline()
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
                            else GERRIT_STATS_BUCKET_KEY.format(
                                ldap=ldap, bucket=bucket
                            )
                        )
                        pipeline.hgetall(key)
                        gerrit_stats_count_map[key] = (ldap, proj, bucket)
            else:
                key = GERRIT_STATS_ALL_TIME_KEY.format(ldap=ldap)
                pipeline.hgetall(key)
                gerrit_stats_count_map[key] = (ldap, None, None)

        results = self.retry_utils.get_retry_on_transient(pipeline.execute)

        stats = {ldap: {f: 0 for f in GERRIT_STAT_FIELDS} for ldap in ldap_list}

        for (key, (ldap, _, _)), data in zip(gerrit_stats_count_map.items(), results):
            for field in GERRIT_STAT_FIELDS:
                if field in data:
                    stats[ldap][field] += int(data[field])

        return stats
