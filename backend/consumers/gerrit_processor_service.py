import json
from backend.common.constants import (
    GERRIT_PROJECTS_KEY,
    GERRIT_DEDUPE_REVIEWED_KEY,
    GERRIT_UNMERGED_CL_KEY_BY_PROJECT,
    GERRIT_PERSUBMIT_BOT,
    GERRIT_CL_REVIEWED_FIELD,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GerritChangeStatus,
    THREE_MONTHS_IN_SECONDS,
    GERRIT_STATUS_TO_FIELD_TEMPLATE,
    GERRIT_LOC_MERGED_FIELD,
    GERRIT_STATS_BUCKET_KEY,  # Import the global key constant
    GERRIT_UNMERGED_CL_KEY_GLOBAL,  # Import the global unmerged CL key constant
)


class GerritProcessorService:
    def __init__(
        self,
        logger,
        redis_client,
        pubsub_puller_factory,
        retry_utils,
        date_time_util,
    ):
        """
        Args:
            logger: Logger instance.
            redis_client: Redis client instance.
            pubsub_puller_factory: Factory that creates PubSubPuller(project_id, subscription_id).
            retry_utils: Retry utility.
            date_time_util: A DateTimeUtil instance for handling date and time operations.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.pubsub_puller_factory = pubsub_puller_factory
        self.retry_utils = retry_utils
        self.date_time_util = date_time_util

    def _get_unmerged_cl_key(self, owner_ldap: str, project: str, status: str) -> str:
        """Generate Redis sorted set key for unmerged CLs (project-specific)"""
        return GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
            ldap=owner_ldap, project=project, cl_status=status
        )

    def _get_unmerged_cl_key_global(self, owner_ldap: str, status: str) -> str:
        """Generate Redis sorted set key for unmerged CLs (global)"""
        return GERRIT_UNMERGED_CL_KEY_GLOBAL.format(ldap=owner_ldap, cl_status=status)

    def _extract_and_validate_change_data(
        self, payload: dict, required_fields: list
    ) -> dict | None:
        """
        Extracts common change-related data from the payload and validates required fields.

        Args:
            payload: The Pub/Sub event payload.
            required_fields: A list of strings, e.g., ["change_number", "project", "owner_ldap"].

        Returns:
            A dictionary with extracted data or None if validation fails.
        """
        change_info = payload.get("change", {})
        status_str = change_info.get("status")
        data = {
            "change_number": change_info.get("number"),
            "project": change_info.get("project"),
            "owner_ldap": change_info.get("owner", {}).get("username"),
            "cl_created_unix_timestamp": change_info.get(
                "createdOn"
            ),  # CL created timestamp
            "event_unix_timestamp": payload.get(
                "eventCreatedOn"
            ),  # Event created timestamp
            "is_private": change_info.get("private"),
            "is_wip": change_info.get("wip"),
            "patch_set_number": payload.get("patchSet", {}).get("number"),
            "insertions": payload.get("patchSet", {}).get("sizeInsertions", 0),
            "change_status": (
                GerritChangeStatus(status_str.lower()) if status_str else None
            ),
        }

        missing_fields = [field for field in required_fields if data.get(field) is None]
        if missing_fields:
            self.logger.warning(
                "Skipping event due to missing essential fields: %s. Payload: %s",
                ", ".join(missing_fields),
                json.dumps(payload),
            )
            return None
        return data

    def _remove_cl_from_unmerged_sets(
        self,
        pipeline,
        owner_ldap: str,
        project: str,
        change_number: int,
        status: GerritChangeStatus,
    ) -> None:
        """Removes a CL from specified unmerged status sorted sets (project-specific and global)."""
        status_value = status.value
        key_project = self._get_unmerged_cl_key(owner_ldap, project, status_value)
        key_global = self._get_unmerged_cl_key_global(owner_ldap, status_value)
        pipeline.zrem(key_project, change_number)
        pipeline.zrem(key_global, change_number)
        self.logger.debug(
            "Pipeline: zrem CL %s from project_key: %s, global_key: %s",
            change_number,
            key_project,
            key_global,
        )

    def _add_cl_to_unmerged_sets(
        self,
        pipeline,
        owner_ldap: str,
        project: str,
        change_number: int,
        status: GerritChangeStatus,
        score: int,
    ) -> None:
        """Adds a CL to specified unmerged status sorted sets (project-specific and global)."""
        status_value = status.value
        key_project = self._get_unmerged_cl_key(owner_ldap, project, status_value)
        key_global = self._get_unmerged_cl_key_global(owner_ldap, status_value)
        pipeline.zadd(key_project, {change_number: score})
        pipeline.zadd(key_global, {change_number: score})
        self.logger.debug(
            "Pipeline: zadd CL %s to project_key: %s, global_key: %s with score %s",
            change_number,
            key_project,
            key_global,
            score,
        )

    def _handle_comment_added(self, payload: dict) -> None:
        """
        Process "comment-added" Pub/Sub events to track reviewer contributions.
        Increments the weekly "cl_reviewed" statistic for the commenter in Redis,
        ensuring each user is counted only once per change via a deduplication set.
        Updates both project-specific and global statistics.
        """
        data = self._extract_and_validate_change_data(
            payload, ["change_number", "project", "owner_ldap", "event_unix_timestamp"]
        )
        if not data:
            return

        owner = data["owner_ldap"]

        commenter = payload.get("author", {}).get("username")
        if not commenter or commenter == GERRIT_PERSUBMIT_BOT or commenter == owner:
            return

        change_number = data["change_number"]
        project = data["project"]
        event_unix_timestamp = data["event_unix_timestamp"]
        dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=change_number)

        # Check for deduplication before performing any Redis operations
        has_reviewed = self.redis_client.sismember(dedupe_key, commenter)
        if has_reviewed:
            self.logger.info(
                "Skipping duplicate count for CL %s, user %s has already reviewed it",
                change_number,
                commenter,
            )
            return

        bucket = self.date_time_util.compute_buckets_weekly(event_unix_timestamp)

        pipeline = self.redis_client.pipeline()

        # Update project-specific weekly stats
        user_weekly_stats_key_project = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
            ldap=commenter, project=project, bucket=bucket
        )
        pipeline.hincrby(user_weekly_stats_key_project, GERRIT_CL_REVIEWED_FIELD, 1)

        # Update global weekly stats
        user_weekly_stats_key_global = GERRIT_STATS_BUCKET_KEY.format(
            ldap=commenter, bucket=bucket
        )
        pipeline.hincrby(user_weekly_stats_key_global, GERRIT_CL_REVIEWED_FIELD, 1)

        # Add to deduplication set
        pipeline.sadd(dedupe_key, commenter)
        pipeline.expire(dedupe_key, THREE_MONTHS_IN_SECONDS)

        self.retry_utils.get_retry_on_transient(pipeline.execute)
        self.logger.info(
            "Updated review stats: user %s reviewed CL %s (project: %s), incremented '%s' in %s and %s",
            commenter,
            change_number,
            project,
            GERRIT_CL_REVIEWED_FIELD,
            user_weekly_stats_key_project,
            user_weekly_stats_key_global,
        )

    def store_payload(self, payload: dict):
        """
        Processes Gerrit Pub/Sub events and updates Redis storage accordingly.

        Depending on the event type, this method delegates to specific handlers to:
        - Track project creation (add to project set).
        - Update change status (new, merged, abandoned) and related metrics.
        - Count reviewer contributions (with deduplication for repeated comments).

        Key Handling Logic:
        - "comment-added": Increments weekly review stats for commenters (once per user/change).
        - "project-created": Adds new project to the global project set.
        - "patchset-created": Tracks new changes (patchset 1) as "under review".
        - "change-merged": Updates merged status, aggregates lines of code (LOC) and counts.
        - "change-abandoned"/"change-restored": Updates change status between abandoned/new.
        - Unsupported types: Logs a warning without further action.

        Args:
            payload (dict): The raw Pub/Sub message data, must include:
                - "type": e.g. "comment-added" or "change-merged" etc.
                - "change": Gerrit change dict (with owner, number, project, created).
                - For comment events: top-level "author" field with "username".
        Raises:
            ValueError: if Redis client is unavailable.

        ToDo:
            [Refactor GerritProcessorService to Abstract Event Handling] | https://jira.circlecat.org/browse/PUR-252
        """
        event_type = payload.get("type")

        if event_type == "comment-added":
            self._handle_comment_added(payload)
        elif event_type == "project-created":
            project_name = payload.get("projectName")
            if project_name:
                self.retry_utils.get_retry_on_transient(
                    lambda: self.redis_client.sadd(GERRIT_PROJECTS_KEY, project_name)
                )
                self.logger.info("Added new project to set: %s", project_name)

        elif event_type == "patchset-created":
            self._handle_patchset_created(payload)
        elif event_type == "change-merged":
            self._handle_change_merged(payload)
        elif event_type == "change-abandoned":
            self._handle_change_abandoned(payload)
        elif event_type == "change-restored":
            self._handle_change_restored(payload)
        elif event_type == "change-deleted":
            self._handle_change_deleted(payload)
        elif event_type in ["private-state-changed", "wip-state-changed"]:
            self._handle_private_and_wip_states_changed(payload)
        else:
            self.logger.warning("Unsupported Gerrit event type: %s", event_type)

    def _handle_private_and_wip_states_changed(self, payload: dict) -> None:
        """
        Handle "private-state-changed" or "wip-state-changed" events.

        This method updates Redis tracking sets to reflect whether a CL (change list) should be considered
        under review or temporarily hidden from reviewers. When a CL becomes private or marked as WIP,
        it is removed from the "unmerged" tracking sets. When it becomes public and not WIP,
        it is re-added as a new change ready for review.
        """
        data = self._extract_and_validate_change_data(
            payload,
            [
                "change_number",
                "project",
                "owner_ldap",
                "cl_created_unix_timestamp",
                "event_unix_timestamp",
            ],
        )
        if not data:
            return

        change_number = data["change_number"]
        project = data["project"]
        owner_ldap = data["owner_ldap"]
        cl_created_unix_timestamp = data["cl_created_unix_timestamp"]
        event_unix_timestamp = data["event_unix_timestamp"]
        is_private = data["is_private"]
        is_wip = data["is_wip"]

        pipeline = self.redis_client.pipeline()

        if is_private or is_wip:
            # The CL became private or WIP — remove it from review tracking sets.
            # Private: only the owner can see it.
            # WIP: not ready for review yet.
            self._remove_cl_from_unmerged_sets(
                pipeline, owner_ldap, project, change_number, GerritChangeStatus.NEW
            )

        else:
            # The CL became public and is no longer WIP — add it back for review tracking.
            self._add_cl_to_unmerged_sets(
                pipeline,
                owner_ldap,
                project,
                change_number,
                GerritChangeStatus.NEW,
                cl_created_unix_timestamp,
            )
            self.logger.info(
                "CL %s (project: %s) became public and not WIP at %s; tracked as NEW (score: %s).",
                change_number,
                project,
                event_unix_timestamp,
                cl_created_unix_timestamp,
            )

        self.retry_utils.get_retry_on_transient(pipeline.execute)

    def _handle_change_deleted(self, payload: dict) -> None:
        """
        Handle "change-deleted" events to remove the CL from all unmerged tracking sets.
        """
        data = self._extract_and_validate_change_data(
            payload, ["change_number", "project", "owner_ldap", "change_status"]
        )
        if not data:
            return

        change_number = data["change_number"]
        project = data["project"]
        owner_ldap = data["owner_ldap"]
        original_change_status = data["change_status"]

        pipeline = self.redis_client.pipeline()

        self._remove_cl_from_unmerged_sets(
            pipeline, owner_ldap, project, change_number, original_change_status
        )

        self.retry_utils.get_retry_on_transient(pipeline.execute)
        self.logger.info("Deleted CL: %s ", change_number)

    def _handle_patchset_created(self, payload: dict) -> None:
        """
        Handle "patchset-created" events to track new changes under review.

        Logic:
        - Only processes the first patchset (patchSet.number == 1) to avoid counting updates/revisions.
        - Adds the new change to Redis sorted sets (project-specific and global) with its creation timestamp,
          tracking it as "under review" (status: NEW).

        Args:
            payload: Pub/Sub event payload containing:
                - "patchSet": Dict with "number" (patchset version).
                - "change": Dict with change details ("number", "project", "owner").
                - "eventCreatedOn": Unix timestamp when the patchset was created.

        Note:
            Skips processing for non-initial patchsets (e.g., patchset 2+ are code updates, not new changes).
        """
        data = self._extract_and_validate_change_data(
            payload,
            [
                "change_number",
                "project",
                "owner_ldap",
                "cl_created_unix_timestamp",
                "patch_set_number",
            ],
        )
        if not data:
            return

        change_number = data["change_number"]
        project = data["project"]
        owner_ldap = data["owner_ldap"]
        cl_created_unix_timestamp = data["cl_created_unix_timestamp"]
        patch_set_number = data["patch_set_number"]

        if patch_set_number != 1:
            self.logger.info(
                "Skipped non-initial patchset for CL %s (patchset: %s) - only tracking new changes",
                change_number,
                patch_set_number,
            )
            return

        pipeline = self.redis_client.pipeline()

        self._add_cl_to_unmerged_sets(
            pipeline,
            owner_ldap,
            project,
            change_number,
            GerritChangeStatus.NEW,
            cl_created_unix_timestamp,
        )
        self.retry_utils.get_retry_on_transient(pipeline.execute)
        self.logger.info(
            "Tracked new under-review CL: %s (project: %s) as NEW (score: %s).",
            change_number,
            project,
            cl_created_unix_timestamp,
        )

    def _handle_change_merged(self, payload: dict) -> None:
        """
        Handle "change-merged" events to update CL status, merge metrics, and clean up tracking data.

        Core Logic:
        1. Calculates the weekly stats bucket using the merge timestamp.
        2. Updates four key metrics in the owner's weekly stats (via Redis Hash):
           - Increment merged lines of code (LOC) by the patchset's insertion count (project-specific and global).
           - Increment merged CL count for the weekly bucket (project-specific and global).
        3. Removes the CL from the "NEW" status tracking sets (project-specific and global) since it's now merged.
        4. Uses Redis pipeline and retry logic to ensure atomicity and resilience against transient errors.

        Args:
            payload: Pub/Sub event payload containing mandatory fields:
                - "eventCreatedOn": Unix timestamp when the CL was merged.
                - "change": Dict with CL details ("number", "project", "owner" with "username").
                - "patchSet": Dict with "sizeInsertions" (number of lines added in the merged patchset).

        Note:
            - Relies on `_get_unmerged_cl_key` to generate the Redis key for tracking "NEW" status CLs.
            - Metrics are stored in a weekly bucket (via `date_time_util.compute_buckets_weekly`) for time-based aggregation.
            - Ignores missing optional fields (e.g., `insertions` defaults to 0 if not found) to avoid partial failures.
        """
        data = self._extract_and_validate_change_data(
            payload,
            [
                "change_number",
                "project",
                "owner_ldap",
                "event_unix_timestamp",
                "insertions",
            ],
        )
        if not data:
            return

        change_number = data["change_number"]
        project = data["project"]
        owner_ldap = data["owner_ldap"]
        merged_unix_timestamp = data["event_unix_timestamp"]
        insertions = data["insertions"]

        bucket = self.date_time_util.compute_buckets_weekly(merged_unix_timestamp)
        cl_merged_field = GERRIT_STATUS_TO_FIELD_TEMPLATE.format(
            status=GerritChangeStatus.MERGED.value
        )

        pipeline = self.redis_client.pipeline()

        # Update project-specific weekly stats
        user_weekly_stats_key_project = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
            ldap=owner_ldap, project=project, bucket=bucket
        )
        pipeline.hincrby(
            user_weekly_stats_key_project, GERRIT_LOC_MERGED_FIELD, insertions
        )
        pipeline.hincrby(user_weekly_stats_key_project, cl_merged_field, 1)

        # Update global weekly stats
        user_weekly_stats_key_global = GERRIT_STATS_BUCKET_KEY.format(
            ldap=owner_ldap, bucket=bucket
        )
        pipeline.hincrby(
            user_weekly_stats_key_global, GERRIT_LOC_MERGED_FIELD, insertions
        )
        pipeline.hincrby(user_weekly_stats_key_global, cl_merged_field, 1)

        # Remove CL from "NEW" status tracking sets (project-specific and global)
        self._remove_cl_from_unmerged_sets(
            pipeline, owner_ldap, project, change_number, GerritChangeStatus.NEW
        )

        self.retry_utils.get_retry_on_transient(pipeline.execute)
        self.logger.info(
            "Merged CL %s: updated stats (LOC: +%d, merged count: +1) in %s and %s; removed from NEW status tracking sets",
            change_number,
            insertions,
            user_weekly_stats_key_project,
            user_weekly_stats_key_global,
        )

    def _handle_change_abandoned(self, payload: dict) -> None:
        """
        Handle "change-abandoned" events to update CL status from "NEW" to "ABANDONED" in tracking storage.

        Logic:
        1. Moves the abandoned CL from the "NEW" status sorted sets (project-specific and global)
           to the "ABANDONED" status sorted sets (project-specific and global).
        2. Uses the abandonment timestamp as the score in the "ABANDONED" set for time-based tracking.
        3. Executes operations via Redis pipeline with retry logic to ensure atomic status synchronization.

        Args:
            payload: Pub/Sub event payload containing:
                - "eventCreatedOn": Unix timestamp when the CL was abandoned.
                - "change": Dict with CL details ("number", "project", "owner" with "username").

        Note:
            - Relies on `_get_unmerged_cl_key` and `_get_unmerged_cl_key_global` to generate Redis keys
              for both "NEW" and "ABANDONED" status sets.
            - The pipeline ensures the CL is not left in an inconsistent state (either fully moved or retried on failure).
        """
        data = self._extract_and_validate_change_data(
            payload, ["change_number", "project", "owner_ldap", "event_unix_timestamp"]
        )
        if not data:
            return

        change_number = data["change_number"]
        project = data["project"]
        owner_ldap = data["owner_ldap"]
        abandoned_unix_timestamp = data["event_unix_timestamp"]

        pipeline = self.redis_client.pipeline()

        self._remove_cl_from_unmerged_sets(
            pipeline, owner_ldap, project, change_number, GerritChangeStatus.NEW
        )
        self._add_cl_to_unmerged_sets(
            pipeline,
            owner_ldap,
            project,
            change_number,
            GerritChangeStatus.ABANDONED,
            abandoned_unix_timestamp,
        )
        self.retry_utils.get_retry_on_transient(pipeline.execute)
        self.logger.info(
            "Abandoned CL %s (project: %s) at %s: moved from NEW to ABANDONED; cleared dedupe key.",
            change_number,
            project,
            abandoned_unix_timestamp,
        )

    def _handle_change_restored(self, payload: dict) -> None:
        """
        Handle "change-restored" events to update CL status from "ABANDONED" to "NEW" and refresh reviewer tracking.

        Core Logic:
            Moves the restored CL from the "ABANDONED" status sorted sets (project-specific and global)
            back to the "NEW" status sets (project-specific and global),
            using the restoration timestamp as the new score.

            Uses Redis pipeline and retry logic for atomicity and resilience against transient errors.

        Args:
            payload: Pub/Sub event payload containing:
                - "eventCreatedOn": Unix timestamp when the CL was restored.
                - "change": Dict with CL details ("number", "project", "owner" with "username").
        """
        data = self._extract_and_validate_change_data(
            payload,
            [
                "change_number",
                "project",
                "owner_ldap",
                "cl_created_unix_timestamp",
                "event_unix_timestamp",
            ],
        )
        if not data:
            return

        change_number = data["change_number"]
        project = data["project"]
        owner_ldap = data["owner_ldap"]
        cl_created_unix_timestamp = data["cl_created_unix_timestamp"]
        restored_unix_timestamp = data["event_unix_timestamp"]

        pipeline = self.redis_client.pipeline()

        self._remove_cl_from_unmerged_sets(
            pipeline, owner_ldap, project, change_number, GerritChangeStatus.ABANDONED
        )
        self._add_cl_to_unmerged_sets(
            pipeline,
            owner_ldap,
            project,
            change_number,
            GerritChangeStatus.NEW,
            cl_created_unix_timestamp,
        )

        self.retry_utils.get_retry_on_transient(pipeline.execute)
        self.logger.info(
            "Restored CL %s (project: %s) at %s: moved from ABANDONED to NEW (score: %s).",
            change_number,
            project,
            restored_unix_timestamp,
            cl_created_unix_timestamp,
        )

    def _process_message(self, message):
        """
        Process a single Pub/Sub message.

        - Decodes the message data from UTF-8 JSON.
        - Dispatches the resulting payload to `store_payload`.
        - Acknowledges the message on success.
        - Logs and negatively acknowledges the message on failure.

        Args:
            message: A Pub/Sub message object, expected to have:
                - .data (bytes): the raw JSON payload
                - .ack(): method to acknowledge successful processing
                - .nack(): method to signal processing failure
        """
        try:
            payload = json.loads(message.data.decode("utf-8"))
            self.store_payload(payload)
            message.ack()
        except Exception as err:
            self.logger.error(
                "[pull_gerrit] failed to process message %s: %s",
                getattr(message, "message_id", "<no-id>"),
                err,
                exc_info=True,
            )
            message.nack()

    def pull_gerrit(self, project_id: str, subscription_id: str):
        """
        Start pulling Gerrit Pub/Sub messages for the given project and subscription,
        processing each change synchronously via `store_change`.

        Args:
            project_id (str): Google Cloud project ID (non-empty).
            subscription_id (str): Pub/Sub subscription ID (non-empty).

        Raises:
            ValueError: If either `project_id` or `subscription_id` is empty.
        """
        if not project_id:
            raise ValueError("project_id must be a non-empty string")
        if not subscription_id:
            raise ValueError("subscription_id must be a non-empty string")

        puller = self.pubsub_puller_factory.get_puller_instance(
            project_id, subscription_id
        )

        puller.start_pulling_messages(self._process_message)
