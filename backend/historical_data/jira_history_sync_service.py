from backend.common.constants import (
    JiraIssueStatus,
    JIRA_STATUS_ID_MAP,
    JIRA_EXCLUDED_STATUS_ID,
    JIRA_ISSUE_DETAILS_KEY,
    JIRA_LDAP_PROJECT_STATUS_INDEX_KEY,
    JIRA_PROJECTS_KEY,
    JIRA_STORY_POINT_FIELD,
)


class JiraHistorySyncService:
    def __init__(
        self,
        logger,
        jira_client,
        redis_client,
        jira_search_service,
        date_time_util,
        retry_utils,
    ):
        """
        Initialize JiraHistorySyncService.

        Args:
            logger: The logger instance for logging messages.
            jira_client: Jira client instance
            redis_client: Redis client instance
            jira_search_service: JiraSearchService instance
            date_time_util: A DateTimeUtil for date and time operations.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        if logger is None:
            raise ValueError("logger must not be None")
        if jira_client is None:
            raise ValueError("jira_client must not be None")
        if redis_client is None:
            raise ValueError("redis_client must not be None")
        if jira_search_service is None:
            raise ValueError("jira_search_service must not be None")
        if date_time_util is None:
            raise ValueError("date_time_util must not be None")
        if retry_utils is None:
            raise ValueError("retry_utils must not be None")

        self.logger = logger
        self.jira_client = jira_client
        self.redis_client = redis_client
        self.jira_search_service = jira_search_service
        self.date_time_util = date_time_util
        self.retry_utils = retry_utils

    def sync_jira_projects_id_and_name_mapping(self) -> int:
        """
        Fetch all Jira projects and store them in Redis as ID-to-name mapping.

        Returns:
            int: Total number of projects processed
        """
        projects = self.jira_client.projects()
        project_dict = {project.id: project.name for project in projects}

        if not project_dict:
            self.logger.error("No projects found in Jira")
            return 0

        self.logger.info("Fetched %d Jira projects", len(project_dict))

        self.redis_client.delete(JIRA_PROJECTS_KEY)
        self.logger.info("Cleared existing project data in Redis")

        self.redis_client.hset(JIRA_PROJECTS_KEY, mapping=project_dict)
        self.logger.info(
            "Successfully stored %d projects in Redis under key '%s'",
            len(project_dict),
            JIRA_PROJECTS_KEY,
        )

        self.logger.info("Jira projects ID-to-name sync completed successfully")

        return len(project_dict)

    def _preprocess_issue_status(
        self, status_info: dict, issue_key: str
    ) -> JiraIssueStatus | None:
        """
        Convert raw Jira issue status information into a standardized JiraIssueStatus enum,
        while filtering out statuses that should be ignored.

        Args:
            status_info (dict): The status field of a Jira issue, typically containing 'id' and 'name'.
            issue_key (str): The key of the current issue, used for logging purposes.

        Returns:
            JiraIssueStatus | None:
                - Returns the corresponding standardized JiraIssueStatus enum if the status is valid.
                - Returns None if status_info is empty, the status is excluded, or the status is unknown.

        Behavior:
            1. If status_info is empty, returns None and logs a debug message.
            2. If status_id equals JIRA_EXCLUDED_STATUS_ID (obsolete status), returns None and logs a debug message.
            3. If status_id is not found in JIRA_STATUS_ID_MAP (unknown status), returns None and logs a debug message.
            4. Otherwise, returns the standardized JiraIssueStatus.
        """
        if not status_info:
            self.logger.debug(
                "Received empty status_info for '%s'. Returning None.", issue_key
            )
            return None

        status_id = status_info.get("id", "")
        if JIRA_EXCLUDED_STATUS_ID == status_id:
            self.logger.debug("Skipping obsoleted issue'%s'.", issue_key)
            return None

        standard_status = JIRA_STATUS_ID_MAP.get(status_id)
        if not standard_status:
            self.logger.debug("Skipping unknown status issue'%s'.", issue_key)
            return None
        return standard_status

    def _get_finish_date_for_done_status(
        self, issue_key: str, issue_id: str, fields: dict
    ) -> int:
        """
        Determine the finish date of a Jira issue that has a DONE status.

        This method attempts to return the most accurate timestamp representing when the issue was completed.
        It first checks the 'resolutiondate' field, and if not available or invalid, it falls back to
        'updated' or 'created' fields in that order.

        Args:
            issue_key (str): The key of the Jira issue (e.g., "PROJ-123"), used for logging.
            issue_id (str): The unique Jira issue ID, used for logging.
            fields (dict): The Jira issue's fields dictionary, which may contain 'resolutiondate',
                        'updated', and 'created' timestamps as strings.

        Returns:
            int:
                - An integer representing the timestamp (after conversion by `date_time_util.format_datetime_str_to_int`)
                of the finish date if determinable.

        Behavior:
            1. If 'resolutiondate' exists and can be parsed, it is used as the finish date.
            2. If 'resolutiondate' is missing or invalid:
                - The method tries 'updated' and then 'created' fields as fallbacks.
                - Logs debug messages when a fallback field is used.
                - Logs warnings if a field exists but cannot be parsed.
        """
        finish_date = None
        resolution_date_str = fields.get("resolutiondate")

        if resolution_date_str:
            finish_date = self.date_time_util.format_datetime_str_to_int(
                resolution_date_str
            )
        if finish_date is None:
            for date_field_name in ["updated", "created"]:
                date_value_str = fields.get(date_field_name)
                if date_value_str:
                    potential_finish_date = (
                        self.date_time_util.format_datetime_str_to_int(date_value_str)
                    )
                    if potential_finish_date is not None:
                        finish_date = potential_finish_date
                        self.logger.debug(
                            "Issue '%s' (ID: %s) has DONE status but no valid 'resolutiondate'. Using '%s' date instead.",
                            issue_key,
                            issue_id,
                            date_field_name,
                        )
                        break
        return finish_date

    def _queue_issues_in_redis_pipeline(self, issues: list, pipeline) -> int:
        """
        Prepare Redis commands to store a batch of Jira issues, including their details and index keys.

        Note:
            This method **only adds commands to the provided Redis pipeline**.
            It does not execute them. To actually write to Redis, the caller must call `pipeline.execute()`.

        Each issue is validated, transformed, and queued in the pipeline:
            - Issue details are stored as Hash under a key formatted by JIRA_ISSUE_DETAILS_KEY.
            - Index keys are updated:
                - DONE issues are added to a sorted set (ZADD) with finish_date as the score.
                - Non-DONE issues are added to a set (SADD).

        Args:
            issues (list): A list of Jira issue objects.
            pipeline: A Redis pipeline object to batch commands for efficiency.

        Returns:
            int: The number of issues successfully queued in the pipeline.

        Behavior:
            1. Skips issues with missing `id`, `key`, or `project_id` and logs a warning.
            2. Skips issues with no assignee (LDAP) and logs a warning.
            3. Uses `_preprocess_issue_status` to standardize the issue status.
                - Skips issues if the status is excluded or unrecognized.
            4. For DONE issues, determines `finish_date` using `_get_finish_date_for_done_status`.
            5. Adds Redis commands to the pipeline:
                - DONE → ZADD with finish_date as score.
                - Non-DONE → SADD.
            6. Logs debug messages for each queued operation.
        """
        stored_count = 0
        for issue in issues:
            issue_raw_data = issue.raw
            issue_key = issue_raw_data.get("key")
            if not issue_key:
                self.logger.warning(
                    "Skipping an issue because 'key' field is missing in raw data: %s",
                    issue_raw_data,
                )
                continue
            issue_id = issue_raw_data.get("id")
            if not issue_id:
                self.logger.warning(
                    "Skipping issue '%s': Issue ID is missing in raw data.", issue_key
                )
                continue

            fields = issue_raw_data.get("fields", {})
            project_info = fields.get("project", {})
            project_id = project_info.get("id")
            if not project_id:
                self.logger.warning(
                    "Skipping issue '%s': Project ID is missing.", issue_key
                )
                continue

            ldap_info = fields.get("assignee")
            if not ldap_info:
                self.logger.warning(
                    "Skipping issue '%s': Assignee is None (possibly the account has been deactivated)",
                    issue_key,
                )
                continue
            ldap = ldap_info.get("name")

            status_info = fields.get("status", {})
            standard_status = self._preprocess_issue_status(status_info, issue_key)
            if standard_status is None:
                self.logger.warning(
                    "Skipping issue '%s': Status could not be processed or is excluded.",
                    issue_key,
                )
                continue

            issue_detail_info = {
                "issue_key": issue_key,
                "issue_title": fields.get("summary", ""),
                "project_id": project_id,
                "story_point": fields.get(JIRA_STORY_POINT_FIELD) or 0.0,
                "issue_status": standard_status.value,
                "ldap": ldap,
            }

            if JiraIssueStatus.DONE == standard_status:
                finish_date = self._get_finish_date_for_done_status(
                    issue_key, issue_id, fields
                )
                issue_detail_info["finish_date"] = finish_date

            issue_detail_info_redis_key = JIRA_ISSUE_DETAILS_KEY.format(
                issue_id=issue_id
            )
            pipeline.hset(issue_detail_info_redis_key, mapping=issue_detail_info)
            self.logger.debug(
                "Pipeline: Added hash for issue '%s' (ID: %s) under key '%s'.",
                issue_key,
                issue_id,
                issue_detail_info_redis_key,
            )

            index_key = JIRA_LDAP_PROJECT_STATUS_INDEX_KEY.format(
                ldap=ldap,
                project_id=project_id,
                status=standard_status.value,
            )

            if JiraIssueStatus.DONE == standard_status:
                pipeline.zadd(index_key, {issue_id: finish_date})
                self.logger.debug(
                    "Pipeline: Added ZADD for DONE issue '%s' (ID: %s) with finish_date %s to index '%s'.",
                    issue_key,
                    issue_id,
                    finish_date,
                    index_key,
                )
            else:
                pipeline.sadd(index_key, issue_id)
                self.logger.debug(
                    "Pipeline: Added SADD for non-DONE issue '%s' (ID: %s) to index '%s'.",
                    issue_key,
                    issue_id,
                    index_key,
                )

            stored_count += 1
        return stored_count

    def backfill_all_jira_issues(self) -> int:
        """
        Backfill all assigned Jira issues into Redis.

        This method retrieves all assigned Jira issues in batches, queues them into a Redis pipeline
        using `_queue_issues_in_redis_pipeline`, and then executes the pipeline to persist the data.

        Returns:
            int: Total number of issues successfully stored in Redis.

        Behavior:
            1. Fetches assigned Jira issues in paginated batches.
            2. For each batch:
                - Creates a Redis pipeline.
                - Queues the batch into the pipeline (commands are prepared but not yet executed).
                - Executes the pipeline to actually write to Redis.
                - Logs the number of issues stored for the batch.
            3. Logs the total number of issues stored after all batches are processed.
        """
        total_stored = 0
        for issues_batch in self.jira_search_service.fetch_assigned_issues_paginated():
            pipeline = self.redis_client.pipeline()
            stored_count = self._queue_issues_in_redis_pipeline(issues_batch, pipeline)
            self.logger.info(
                f"Stored {stored_count} issues (batch size: {len(issues_batch)})"
            )
            self.retry_utils.get_retry_on_transient(pipeline.execute)
            total_stored += stored_count

        self.logger.info(f"Backfill complete. Total issues stored: {total_stored}")
        return total_stored

    def process_update_jira_issues(self, hours: int) -> int:
        """
        Processes Jira issues updated within a specified number of hours.

        This method handles four main update scenarios:
        1. A task created long ago but recently assigned (not in Redis, needs to be saved).
        2. An unassigned task with updated content (not in Redis, remains unsaved).
        3. A previously assigned task that is now unassigned (needs to be removed from Redis).
        4. A previously assigned task with updated content (needs to be updated in Redis).

        Args:
            hours (int): The number of hours to look back for updated Jira issues.

        Returns:
            int: The total number of issues processed and stored/updated in Redis.
        """
        total_processed = 0
        self.logger.info(
            "Starting to process Jira issues updated within the last %s hours", hours
        )

        for (
            issues_batch
        ) in self.jira_search_service.fetch_issues_updated_within_hours_paginated(
            hours
        ):
            issue_ids = [issue.raw.get("id") for issue in issues_batch]

            search_pipeline = self.redis_client.pipeline()
            for issue_id in issue_ids:
                search_pipeline.hgetall(
                    JIRA_ISSUE_DETAILS_KEY.format(issue_id=issue_id)
                )
            old_issue_detail_raw = self.retry_utils.get_retry_on_transient(
                search_pipeline.execute
            )

            updated_pipeline = self.redis_client.pipeline()
            issues_to_store = []

            for i, issue in enumerate(issues_batch):
                issue_raw_data = issue.raw
                issue_id = issue_raw_data.get("id")
                fields = issue_raw_data.get("fields", {})
                new_ldap = None
                assignee_info = fields.get("assignee", {})
                if assignee_info:
                    new_ldap = assignee_info.get("name")

                old_raw_data = old_issue_detail_raw[i]
                if old_raw_data is None:
                    if new_ldap:
                        self.logger.info(
                            "Issue '%s' was recently assigned and will be stored.",
                            issue_id,
                        )
                        issues_to_store.append(issue)
                    else:
                        self.logger.info(
                            "Issue '%s' remains unassigned; skipping.", issue_id
                        )
                    continue

                old_ldap = old_raw_data.get("ldap")
                old_project_id = old_raw_data.get("project_id")
                old_status = old_raw_data.get("issue_status")

                if new_ldap is None and old_ldap:
                    self.logger.info(
                        "Assignee for issue '%s' was removed. Deleting from Redis.",
                        issue_id,
                    )
                    updated_pipeline.delete(
                        JIRA_ISSUE_DETAILS_KEY.format(issue_id=issue_id)
                    )
                    index_key = JIRA_LDAP_PROJECT_STATUS_INDEX_KEY.format(
                        ldap=old_ldap, project_id=old_project_id, status=old_status
                    )
                    if JiraIssueStatus.DONE.value == old_status:
                        updated_pipeline.zrem(index_key, issue_id)
                    else:
                        updated_pipeline.srem(index_key, issue_id)
                    continue

                if new_ldap:
                    index_key = JIRA_LDAP_PROJECT_STATUS_INDEX_KEY.format(
                        ldap=old_ldap, project_id=old_project_id, status=old_status
                    )
                    if JiraIssueStatus.DONE.value == old_status:
                        updated_pipeline.zrem(index_key, issue_id)
                    else:
                        updated_pipeline.srem(index_key, issue_id)

                    self.logger.info(
                        "Content for issue '%s' has been updated; will re-store.",
                        issue_id,
                    )
                    issues_to_store.append(issue)

            if issues_to_store:
                self.logger.info(
                    "Storing/updating %d issues in Redis.", len(issues_to_store)
                )
                self._queue_issues_in_redis_pipeline(issues_to_store, updated_pipeline)

            self.retry_utils.get_retry_on_transient(updated_pipeline.execute)
            total_processed += len(issues_to_store)

        self.logger.info(
            "Processing complete. Total issues stored/updated: %s", total_processed
        )
        return total_processed
