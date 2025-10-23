import calendar
from datetime import datetime
from typing import Generator
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
    GERRIT_STATS_BUCKET_KEY,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GERRIT_DEDUPE_REVIEWED_KEY,
    GERRIT_PROJECTS_KEY,
    GERRIT_CHANGE_STATUS_KEY,
    DATETIME_FORMAT_YMD_HMS,
    GERRIT_UNMERGED_CL_KEY_BY_PROJECT,
    GERRIT_PERSUBMIT_BOT,
    GERRIT_STATUS_TO_FIELD_TEMPLATE,
    THREE_MONTHS_IN_SECONDS,
    GERRIT_UNMERGED_CL_KEY_GLOBAL,
)


class GerritSyncService:
    def __init__(
        self, logger, redis_client, gerrit_client, retry_utils, date_time_util
    ):
        """
        Args:
            logger: Logger instance.
            redis_client: Redis client instance.
            gerrit_client: Gerrit client instance.
            retry_utils: Retry utility for transient failures.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.gerrit_client = gerrit_client
        self.retry_utils = retry_utils
        self.date_time_util = date_time_util

    def fetch_changes(
        self,
        statuses: list[str] | None = None,
        projects: list[str] | None = None,
        max_changes: int | None = None,
        page_size: int = 500,
    ) -> Generator[list[dict], None, None]:
        """
        Generator that pages through Gerrit changes using the Gerrit REST API.

        Args:
            statuses (list[str] | None): Optional list of change statuses to filter by
                (e.g., ["merged", "abandoned", "open"]). If None, all statuses are considered.
            projects (list[str] | None): Optional list of project names to filter by. If None, all projects are considered.
            max_changes (int | None): Maximum number of changes to return. If None, fetches all matching changes.
            page_size (int): Number of results to fetch per API request. Defaults to 500.

        Yields:
            list[dict]: A list of Gerrit change records for each fetched page.

        Example:
            list(fetch_changes(statuses=["merged", "abandoned"], projects=["purrf"], limit=1000, page_size=500))

            This translates to a query like:
            q=(status:merged OR status:abandoned) project:purrf&n=500&S=0
            (then continues pagination with S=500, S=1000, etc., until 1000 total changes are fetched)
        """
        total_fetched = 0
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
            current_page_limit = page_size
            if max_changes is not None:
                remaining_to_fetch = max_changes - total_fetched
                if remaining_to_fetch <= 0:
                    break
                current_page_limit = min(page_size, remaining_to_fetch)

            if current_page_limit == 0:
                break

            page = self.gerrit_client.query_changes(
                queries=queries or [],
                limit=current_page_limit,
                start=start,
                no_limit=False,
                options=[
                    "DETAILED_ACCOUNTS",
                    "MESSAGES",
                ],
                allow_incomplete=True,
            )
            if not page:
                break

            yield page

            if max_changes is not None and total_fetched >= max_changes:
                break
            if len(page) < page_size:
                break

            start += page_size

    def compute_buckets(self, created_str: str) -> str:
        """
        Compute monthly bucket key from Gerrit 'created' timestamp.
        Returns a string "YYYY-MM-DD_YYYY-MM-DD".
        """
        try:
            dt = datetime.strptime(created_str.split(".")[0], DATETIME_FORMAT_YMD_HMS)
        except ValueError:
            dt = datetime.utcnow()
        year, month = dt.year, dt.month
        start = datetime(year, month, 1).date()
        last = calendar.monthrange(year, month)[1]
        end = datetime(year, month, last).date()
        return GERRIT_DATE_BUCKET_TEMPLATE.format(start=start, end=end)

    def store_change(self, change: dict) -> None:
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
                datetime.fromtimestamp(ts).strftime(DATETIME_FORMAT_YMD_HMS)
                if ts
                else ""
            )
        bucket = self.compute_buckets(created_str)

        new_tab = (
            GERRIT_UNDER_REVIEW if state in GERRIT_UNDER_REVIEW_STATUS_VALUES else state
        )
        new_cl_tab = GERRIT_STATUS_TO_FIELD.get(new_tab, f"cl_{new_tab}")

        self.logger.debug("ldap: %s", ldap)
        self.logger.debug("cl_%s", new_tab)
        self.logger.debug("bucket: %s", bucket)

        # all-time stats
        all_time_stats_key = GERRIT_STATS_ALL_TIME_KEY.format(ldap=ldap)
        # monthly bucket
        monthly_bucket_key = GERRIT_STATS_BUCKET_KEY.format(ldap=ldap, bucket=bucket)
        # project-scoped bucket
        project_scoped_bucket_key = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
            ldap=ldap, project=project, bucket=bucket
        )

        pipe = self.redis_client.pipeline()

        review_dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(
            change_number=change_number
        )
        participants = {
            m["author"]["username"]
            for m in change.get("messages", [])
            if m.get("author", {}).get("username") and m["author"]["username"] != ldap
        }
        existing = self.redis_client.smembers(review_dedupe_key) or set()

        for user in participants - existing:
            self.bump_cl_reviewed(pipe, user, project, bucket)

        pipe.expire(review_dedupe_key, 60 * 60 * 24 * 90)
        pipe.execute()

        prev_tab = self.redis_client.hget(GERRIT_CHANGE_STATUS_KEY, change_number)
        if prev_tab == new_tab:
            self.logger.debug(
                "CL %s already seen as %s; skipping", change_number, new_tab
            )
            return

        pipe = self.redis_client.pipeline()
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

    def bump_cl_reviewed(self, pipe, user: str, project: str, bucket: str) -> None:
        """
        Add +1 to cl_reviewed for a given user across all‐time, monthly, and project scopes.
        """
        key_all = GERRIT_STATS_ALL_TIME_KEY.format(ldap=user)
        key_month = GERRIT_STATS_BUCKET_KEY.format(ldap=user, bucket=bucket)
        key_proj = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
            ldap=user, project=project, bucket=bucket
        )

        for k in (key_all, key_month, key_proj):
            pipe.hincrby(k, GERRIT_CL_REVIEWED_FIELD, 1)

    def _aggregate_single_change(
        self,
        change: dict,
        user_weekly_stats: dict,
        global_unmerged_cl_data: dict,
        under_review_dedupe_data: dict,
    ):
        """
        Aggregate statistics for a single Gerrit change (CL).

        This method updates weekly statistics for both the CL owner and reviewers.
        All reviewers who participated in reviewing the CL are aggregated,
        regardless of the CL"s current status. For users who reviewed multiple times,
        the earliest review time is used for weekly bucketing.

        For merged CLs:
            - Updates the owner"s weekly count of merged CLs (project-specific and global).
            - Updates the owner"s weekly total lines of code added (insertions) (project-specific and global).

        For unmerged ( new and abandon ) CLs:
            - Tracks the reviewers who participated in reviewing the CL.
            - Uses the earliest review time for users who reviewed multiple times.
            - Updates a deduplicated mapping of under-review CLs per change number.
            - Stores unmerged CLs in global sorted sets keyed by owner and CL status
              (project-specific and global), with the last updated timestamp as the score.

        Skips aggregation for CLs owned by the automation bot (GERRIT_PERSUBMIT_BOT)
        or for CLs missing required fields (owner, change number, or project).

        Parameters:
            change : dict
                A dictionary representing a Gerrit change (CL), containing fields like
                "owner", "status", "project", "virtual_id_number", "messages", "submitted",
                "updated", and "insertions".

            user_weekly_stats : dict
                A dictionary mapping keys of the form
                "gerrit:stats:{ldap}:{project}:{week_bucket}" and "gerrit:stats:{ldap}:{week_bucket}"
                to another dict containing aggregated statistics (e.g., number of merged CLs,
                lines of merged code, review counts) per user per week.

            global_unmerged_cl_data : dict
                A dictionary mapping keys of the form
                "gerrit:cl:{ldap}:{project}:{cl_status}" and "gerrit:cl:{ldap}:{cl_status}"
                to another dict mapping unmerged CL numbers to their last updated timestamp
                (used for global tracking of unmerged CLs).

            under_review_dedupe_data : dict
                A dictionary mapping change numbers to sets of reviewer usernames who
                have reviewed the CL, used to deduplicate reviewer contributions.

        Returns: None
            The function updates the provided dictionaries in-place and does not return a value.
        """

        owner_ldap = change.get("owner", {}).get("username")
        cl_status = change.get("status", "").lower()
        project = change.get("project")
        change_number = change.get("virtual_id_number")

        if GERRIT_PERSUBMIT_BOT == owner_ldap:
            self.logger.info(
                "Skipping aggregation for CL %s because owner is CatBot.", change_number
            )
            return None

        if not owner_ldap or not change_number or not project:
            self.logger.warning(
                "Missing required fields (owner_ldap, change_number, or project) in change number: %s. Skipping aggregation.",
                change_number,
            )
            return None

        # Aggregate reviewers of this CL.
        # Get all participants in messages, filtering out the owner and CatBot directly.
        # These are the actual human reviewers.
        # If they reviewed multiple times, use the earliest review time.
        participant_first_message_date = {}
        for m in change.get("messages", []):
            username = m.get("author", {}).get("username")
            if username and username != owner_ldap and username != GERRIT_PERSUBMIT_BOT:
                message_date_str = m["date"]

                message_date = self.date_time_util.parse_timestamp_without_microseconds(
                    message_date_str
                )
                if (
                    username not in participant_first_message_date
                    or message_date < participant_first_message_date[username]
                ):
                    participant_first_message_date[username] = message_date

        review_participants: set[str] = set(participant_first_message_date.keys())

        for user in review_participants:
            reviewr_bucket = self.date_time_util.compute_buckets_weekly(
                participant_first_message_date[user]
            )

            # 1. Store reviewer stats with project-specific key
            review_key_project = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                ldap=user, project=project, bucket=reviewr_bucket
            )
            if review_key_project not in user_weekly_stats:
                user_weekly_stats[review_key_project] = {}

            user_weekly_stats[review_key_project][GERRIT_CL_REVIEWED_FIELD] = (
                user_weekly_stats[review_key_project].get(GERRIT_CL_REVIEWED_FIELD, 0)
                + 1
            )

            # 2. Store reviewer stats with global key (without project)
            review_key_global = GERRIT_STATS_BUCKET_KEY.format(
                ldap=user, bucket=reviewr_bucket
            )
            if review_key_global not in user_weekly_stats:
                user_weekly_stats[review_key_global] = {}

            user_weekly_stats[review_key_global][GERRIT_CL_REVIEWED_FIELD] = (
                user_weekly_stats[review_key_global].get(GERRIT_CL_REVIEWED_FIELD, 0)
                + 1
            )

        if GerritChangeStatus.MERGED.value == cl_status:
            # Aggregate the number and lines of merged CLs by CL owner.
            submitted_time = change["submitted"]
            bucket = self.date_time_util.compute_buckets_weekly(submitted_time)
            new_cl_tab = GERRIT_STATUS_TO_FIELD_TEMPLATE.format(status=cl_status)
            insertions = change.get("insertions", 0)

            # 1. Store owner's merged CL stats with project-specific key
            owner_key_project = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                ldap=owner_ldap, project=project, bucket=bucket
            )
            if owner_key_project not in user_weekly_stats:
                user_weekly_stats[owner_key_project] = {}

            user_weekly_stats[owner_key_project][new_cl_tab] = (
                user_weekly_stats[owner_key_project].get(new_cl_tab, 0) + 1
            )
            user_weekly_stats[owner_key_project][GERRIT_LOC_MERGED_FIELD] = (
                user_weekly_stats[owner_key_project].get(GERRIT_LOC_MERGED_FIELD, 0)
                + insertions
            )

            # 2. Store owner's merged CL stats with global key (without project)
            owner_key_global = GERRIT_STATS_BUCKET_KEY.format(
                ldap=owner_ldap, bucket=bucket
            )
            if owner_key_global not in user_weekly_stats:
                user_weekly_stats[owner_key_global] = {}

            user_weekly_stats[owner_key_global][new_cl_tab] = (
                user_weekly_stats[owner_key_global].get(new_cl_tab, 0) + 1
            )
            user_weekly_stats[owner_key_global][GERRIT_LOC_MERGED_FIELD] = (
                user_weekly_stats[owner_key_global].get(GERRIT_LOC_MERGED_FIELD, 0)
                + insertions
            )

        else:
            # Handle unmerged changes (e.g., "NEW" or "ABANDONED" statuses)
            # Store reviewers for this change to avoid duplicate review counts
            under_review_dedupe_data[change_number] = review_participants

            # Get the last updated timestamp from the change and parse it
            last_updated_time_str = change["updated"]
            last_updated_datetime = (
                self.date_time_util.parse_timestamp_without_microseconds(
                    last_updated_time_str
                )
            )
            sorted_set_score = last_updated_datetime.timestamp()

            # 1. Store unmerged CL data with project-specific key
            sorted_set_key_project = GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
                ldap=owner_ldap, project=project, cl_status=cl_status
            )
            if sorted_set_key_project not in global_unmerged_cl_data:
                global_unmerged_cl_data[sorted_set_key_project] = {}

            global_unmerged_cl_data[sorted_set_key_project][change_number] = (
                sorted_set_score
            )

            # 2. Store unmerged CL data with global key (without project)
            sorted_set_key_global = GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
                ldap=owner_ldap, cl_status=cl_status
            )
            if sorted_set_key_global not in global_unmerged_cl_data:
                global_unmerged_cl_data[sorted_set_key_global] = {}

            global_unmerged_cl_data[sorted_set_key_global][change_number] = (
                sorted_set_score
            )

    def _batch_store_changes(self, all_changes: list[dict]) -> None:
        """
        Batch process and store Gerrit changes into Redis.

        This method performs in-memory aggregation of statistics for all provided Gerrit changes,
        including:
        - Weekly stats per user (owners and reviewers) for both project-specific and global keys.
        - Deduplicated sets of reviewers for under-review CLs.
        - Global sorted sets of unmerged CLs keyed by owner and status for both project-specific and global keys.

        After aggregation, the data is written to Redis using a single pipeline:
        - HSET for all user weekly statistics
        - SADD + EXPIRE for under-review reviewer deduplication sets
        - ZADD for global unmerged CL data

        Parameters:
            all_changes : list[dict]
                List of Gerrit changes (CLs), where each dict contains fields such as:
                "owner", "status", "project", "virtual_id_number", "messages", "submitted", "updated", "insertions".

        Returns: None
            The method updates Redis in-place using a pipeline. No value is returned.
        """
        if not all_changes:
            self.logger.info("No Gerrit changes to process for batch store.")
            return

        user_weekly_stats: dict = {}
        global_unmerged_cl_data: dict = {}

        # Mapping of under-review CLs to their reviewers for deduplication
        under_review_dedupe_data: dict[int, set[str]] = {}

        for change in all_changes:
            self._aggregate_single_change(
                change,
                user_weekly_stats,
                global_unmerged_cl_data,
                under_review_dedupe_data,
            )

        write_pipe = self.redis_client.pipeline()

        # Queue HSET for all aggregated statistics keys (includes both project-specific and global)
        for key, final_values in user_weekly_stats.items():
            if final_values:
                write_pipe.hset(key, mapping=final_values)

        # Queue SADD + EXPIRE for reviewer deduplication sets (only for under_review CLs)
        for change_number, participants in under_review_dedupe_data.items():
            if not participants:
                continue
            review_dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(
                change_number=change_number
            )
            write_pipe.sadd(review_dedupe_key, *participants)
            write_pipe.expire(review_dedupe_key, THREE_MONTHS_IN_SECONDS)

        # Queue ZADD for global unmerged CL sorted sets (includes both project-specific and global)
        for sorted_set_key, cl_data in global_unmerged_cl_data.items():
            if cl_data:
                write_pipe.zadd(sorted_set_key, cl_data)

        self.retry_utils.get_retry_on_transient(write_pipe.execute)
        self.logger.info(
            "Successfully wrote all aggregated data to Redis in a single pipeline."
        )

    def fetch_and_store_changes(
        self,
        statuses: list[str] | None = None,
        projects: list[str] | None = None,
        max_changes: int | None = None,
        page_size: int = 500,
    ) -> None:
        """
        Orchestrator function that fetches Gerrit changes and stores them in Redis.
        Combines `fetch_changes` and `_batch_store_changes`, logging progress and any errors encountered.

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
            for changes_batch in self.fetch_changes(
                statuses, projects, max_changes, page_size
            ):
                self._batch_store_changes(changes_batch)
                batch_count = len(changes_batch)
                total += batch_count
                self.logger.info(
                    "Processed a batch of %d changes, total processed so far: %d",
                    batch_count,
                    total,
                )

            self.logger.info("Finished processing %d Gerrit changes", total)
        except Exception as e:
            self.logger.error("Error after processing %d changes: %s", total, e)
            raise

    def sync_gerrit_projects(self) -> int:
        """
        Fetches all project names from Gerrit and stores them in a Redis set.

        Returns:
            int: The number of projects synced.
        """
        projects = self.gerrit_client.get_projects() or {}
        if projects:
            self.redis_client.sadd(GERRIT_PROJECTS_KEY, *projects.keys())
        return len(projects)
