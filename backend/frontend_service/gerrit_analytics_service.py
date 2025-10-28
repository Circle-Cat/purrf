import re
from datetime import datetime, timezone
from backend.common.constants import (
    GERRIT_STATS_BUCKET_KEY,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GERRIT_PROJECTS_KEY,
    ZSET_MIN_SCORE,
    GerritChangeStatus,
    GERRIT_UNMERGED_CL_KEY_BY_PROJECT,
    GERRIT_UNMERGED_CL_KEY_GLOBAL,
    GERRIT_CL_MERGED_FIELD,
    GERRIT_CL_ABANDONED_FIELD,
    GERRIT_CL_UNDER_REVIEW_FIELD,
    GERRIT_CL_REVIEWED_FIELD,
    GERRIT_LOC_MERGED_FIELD,
)


class GerritAnalyticsService:
    def __init__(
        self,
        logger,
        redis_client,
        retry_utils,
        ldap_service,
        date_time_util,
        gerrit_client,
    ):
        """
        Gerrit Analytics Service to aggregate stats from Redis.

        Args:
            logger: Logger instance.
            redis_client: The Redis client instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
            ldap_service: Service that can provide active LDAP users.
            date_time_util: A DateTimeUtil instance for handling date and time operations.
            gerrit_client: A Gerrit Client instance.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.retry_utils = retry_utils
        self.ldap_service = ldap_service
        self.date_time_util = date_time_util
        self.gerrit_client = gerrit_client
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

    def get_gerrit_stats(
        self,
        ldap_list: list[str] | None = None,
        start_date_str: str | None = None,
        end_date_str: str | None = None,
        project_list: list[str] | None = None,
        include_full_stats: bool = False,
        include_all_projects: bool = True,
    ) -> dict[str, dict]:
        """
        Aggregate Gerrit stats from Redis buckets, including merged, reviewed,
        abandoned,and under-review change lists (CLs) based on the specified date range and filters.

        The method queries under-review CLs only when the end date of the range matches today's date(UTC).
        For other date ranges, only merged, reviewed, and abandoned CLs are included.

        When project_list is not provided or empty, the method optimizes by queryingglobal (non-project-specific)
        Redis keys for stats.

        Args:
            - ldap_list: List of LDAP usernames to include. If None or empty, fetches all active interns and employees.
            - start_date_str: Beginning of date range (inclusive), e.g., "YYYY-MM-DD".
            - end_date_str: End of date range (inclusive), e.g., "YYYY-MM-DD".
                            Under-review CLs are onlyincluded if this date matches today's UTC date.
            - project_list: Optional list of project names to filter stats by. If None or empty,global stats are retrieved.
            - include_full_stats: Whether to include abandoned and under-review CL counts.
                            When False,only merged and reviewed CL stats are returned.
            - include_all_projects: If True, aggregates stats across all projects
                            using global keys (time- and user-based only), ignoring project_list.

        Returns:
            Dictionary keyed by LDAP username, each containing aggregated statistics with fields:
                GERRIT_CL_MERGED_FIELD: Count of merged CLs
                GERRIT_CL_REVIEWED_FIELD: Count of reviewed CLs
                GERRIT_LOC_MERGED_FIELD: Total lines of code in merged CLs
                GERRIT_CL_ABANDONED_FIELD: Count of abandoned CLs (only if include_full_stats=True)
                GERRIT_CL_UNDER_REVIEW_FIELD: Count of under-review CLs (only if include_full_stats=True
                and end_date matches today's UTC date; otherwise None)
        """
        if not ldap_list:
            ldap_list = self.ldap_service.get_all_active_interns_and_employees_ldaps()
            if not ldap_list:
                self.logger.warning("No active LDAP users found.")
                return {}
            self.logger.info(
                "Loaded all active interns and employees LDAP: %s", len(ldap_list)
            )

        invalid = [ldap for ldap in ldap_list if not self.LDAP_RE.fullmatch(ldap)]
        if invalid:
            raise ValueError(f"Invalid LDAP(s): {invalid}")

        start_date_time, end_date_time = self.date_time_util.get_start_end_timestamps(
            start_date_str, end_date_str
        )
        start_date, end_date = start_date_time.date(), end_date_time.date()

        week_buckets = self.date_time_util.get_week_buckets(
            start=start_date, end=end_date
        )

        today = datetime.now(timezone.utc).date()
        include_under_review = end_date == today
        self.logger.debug(
            "[get_gerrit_stats] include_under_review=%s (today=%s, end_date=%s)",
            include_under_review,
            today,
            end_date,
        )
        # If include_all_projects is True, we want to aggregate stats across all projects.
        # Setting projects = [None] is a convention used later in the loop: when project is None,
        # the code generates global (non-project-specific) Redis keys instead of project-specific keys.
        if include_all_projects:
            projects = [None]
            self.logger.debug(
                "[get_gerrit_stats] include_all_projects=True, using global aggregation."
            )
        else:
            projects = [p for p in (project_list or []) if p] or [None]
            self.logger.debug(
                "[get_gerrit_stats] include_all_projects=False, using project-specific aggregation. projects=%s",
                projects,
            )

        pipeline = self.redis_client.pipeline()
        for ldap in ldap_list:
            for project in projects:
                # weekly stats key
                for bucket in week_buckets:
                    stats_key = (
                        GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                            ldap=ldap, project=project, bucket=bucket
                        )
                        if project
                        else GERRIT_STATS_BUCKET_KEY.format(ldap=ldap, bucket=bucket)
                    )
                    pipeline.hgetall(stats_key)

                if not include_full_stats:
                    continue
                # abandoned CL key
                abandoned_cl_search_key = (
                    GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
                        ldap=ldap,
                        project=project,
                        cl_status=GerritChangeStatus.ABANDONED.value,
                    )
                    if project
                    else GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
                        ldap=ldap, cl_status=GerritChangeStatus.ABANDONED.value
                    )
                )
                pipeline.zcount(
                    abandoned_cl_search_key,
                    start_date_time.timestamp(),
                    end_date_time.timestamp(),
                )

                if not include_under_review:
                    continue

                # under review CL key
                under_reviewed_cl_search_key = (
                    GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
                        ldap=ldap,
                        project=project,
                        cl_status=GerritChangeStatus.NEW.value,
                    )
                    if project
                    else GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
                        ldap=ldap, cl_status=GerritChangeStatus.NEW.value
                    )
                )
                pipeline.zcount(
                    under_reviewed_cl_search_key,
                    ZSET_MIN_SCORE,
                    end_date_time.timestamp(),
                )

        results = self.retry_utils.get_retry_on_transient(pipeline.execute)
        self.logger.debug(
            "[get_gerrit_stats] Pipeline executed, got %d results.", len(results)
        )

        stats = {}

        idx = 0
        for ldap in ldap_list:
            stats[ldap] = {
                GERRIT_CL_MERGED_FIELD: 0,
                GERRIT_CL_ABANDONED_FIELD: 0,
                GERRIT_CL_UNDER_REVIEW_FIELD: 0,
                GERRIT_CL_REVIEWED_FIELD: 0,
                GERRIT_LOC_MERGED_FIELD: 0,
            }
            for project in projects:
                # weekly stats hgetall
                for _ in week_buckets:
                    bucket_data = results[idx]
                    idx += 1
                    stats[ldap][GERRIT_CL_MERGED_FIELD] += int(
                        bucket_data.get(GERRIT_CL_MERGED_FIELD, 0)
                    )
                    stats[ldap][GERRIT_CL_REVIEWED_FIELD] += int(
                        bucket_data.get(GERRIT_CL_REVIEWED_FIELD, 0)
                    )
                    stats[ldap][GERRIT_LOC_MERGED_FIELD] += int(
                        bucket_data.get(GERRIT_LOC_MERGED_FIELD, 0)
                    )

                if not include_full_stats:
                    continue

                abandoned_count = results[idx]
                idx += 1
                stats[ldap][GERRIT_CL_ABANDONED_FIELD] += abandoned_count

                if include_under_review:
                    under_review_count = results[idx]
                    idx += 1
                    stats[ldap][GERRIT_CL_UNDER_REVIEW_FIELD] += under_review_count
                else:
                    stats[ldap][GERRIT_CL_UNDER_REVIEW_FIELD] = None

        self.logger.debug(
            "[get_gerrit_stats] Aggregation complete. Returning stats for %d LDAPs: %s",
            len(stats),
            list(stats.keys()),
        )
        return stats
