from backend.common.constants import (
    JIRA_ISSUE_DETAILS_KEY,
    JIRA_PROJECTS_KEY,
    JiraIssueStatus,
    JIRA_LDAP_PROJECT_STATUS_INDEX_KEY,
)
from itertools import product
from collections import defaultdict


class JiraAnalyticsService:
    def __init__(self, logger, redis_client, date_time_util, ldap_service, retry_utils):
        """
        Initializes the MicrosoftChatAnalyticsService.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            date_time_util: A DateTimeUtil instance for handling date and time operations.
            ldap_service: A LdapService instance for performing LDAP lookups.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.date_time_util = date_time_util
        self.ldap_service = ldap_service
        self.retry_utils = retry_utils

        if not self.logger:
            raise ValueError("Logger not provided.")
        if not self.redis_client:
            raise ValueError("Redis client not created.")
        if not self.retry_utils:
            raise ValueError("Retry utils not provided.")
        if not self.date_time_util:
            raise ValueError("Date time util not provided.")
        if not self.ldap_service:
            raise ValueError("Ldap service not provided.")

    def get_all_jira_projects(self) -> dict[str, str]:
        """
        Retrieve all Jira project names stored in Redis hash 'jira:project'.

        Returns:
            dict[str, str]: Mapping of project_id (as str) to project_name
        """
        project_data = self.retry_utils.get_retry_on_transient(
            self.redis_client.hgetall, JIRA_PROJECTS_KEY
        )
        return project_data

    def get_issues_summary(
        self,
        status_list: list[JiraIssueStatus] | None,
        ldaps: list[str] | None,
        project_ids: list[str] | None,
        start_date: str | None,
        end_date: str | None,
    ) -> dict[str, any]:
        """
        Retrieve a summary of Jira issues grouped by status for given users (ldaps) and projects
        within a specified date range. Optionally calculates the total story points for DONE issues.

        Args:
            status_list : list[JiraIssueStatus] | None
                List of Jira issue statuses to include (e.g., DONE, IN_PROGRESS, TODO).
                If None, defaults to all three.
            ldaps : list[str] | None
                List of user LDAPs to include in the summary. If None, uses all active interns and employees.
            project_ids : list[str] | None
                List of Jira project IDs to include. If None, fetches all available projects.
            start_date : str | None
                Start date of the range (ISO format or other accepted by date_time_util).
                If None, a default range is used.
            end_date : str | None
                End date of the range. If None, a default range is used.

        Returns:
            dict[str, any]
                Dictionary containing:
                - "time_range": dict with ISO formatted 'start_dt' and 'end_dt'.
                - For each ldap:
                    - A list of issue IDs for each requested status.
                    - "done_story_points_total": float, sum of story points for DONE issues (0.0 if none or not requested).

        Example structure:
        {
            "time_range": {
                "start_dt": "2023-01-01T00:00:00+00:00",
                "end_dt": "2023-01-31T23:59:59+00:00"
            },
            "user1": {
                "done": ["done-issue-1", "done-issue-2"],
                "in_progress": ["inprogress-issue-1"],
                "todo": [],
                "done_story_points_total": 8.0
            },
            "user2": {
                "done": [],
                "in_progress": ["inprogress-issue-2"],
                "todo": ["todo-issue-1"],
                "done_story_points_total": 0.0
            }
        }
        """
        start_dt, end_dt = self.date_time_util.get_start_end_timestamps(
            start_date, end_date
        )
        start_score = self.date_time_util.format_datetime_to_int(start_dt)
        end_score = self.date_time_util.format_datetime_to_int(end_dt)

        status_list = status_list or [
            JiraIssueStatus.DONE,
            JiraIssueStatus.IN_PROGRESS,
            JiraIssueStatus.TODO,
        ]
        ldaps = ldaps or self.ldap_service.get_all_active_interns_and_employees_ldaps()
        project_ids = project_ids or self.get_all_jira_projects()

        self.logger.info(
            "Get jira issues summary with status_list=%s, ldaps=%s, project_ids=%s, start_date=%s, end_date=%s",
            status_list,
            ldaps,
            project_ids,
            start_date,
            end_date,
        )

        final_result: dict[str, dict[str, list[str] | float]] = defaultdict(
            lambda: defaultdict(list)
        )
        final_result["time_range"] = {
            "start_dt": start_dt.isoformat(),
            "end_dt": end_dt.isoformat(),
        }
        for ldap in ldaps:
            final_result[ldap]["done_story_points_total"] = 0.0
            for status in [
                JiraIssueStatus.DONE,
                JiraIssueStatus.IN_PROGRESS,
                JiraIssueStatus.TODO,
            ]:
                final_result[ldap][status.value] = []

        first_pipeline = self.redis_client.pipeline()
        request_keys_and_info = []
        should_calculate_story_points = JiraIssueStatus.DONE in status_list

        for ldap, status, project_id in product(ldaps, status_list, project_ids):
            redis_key = JIRA_LDAP_PROJECT_STATUS_INDEX_KEY.format(
                ldap=ldap, project_id=project_id, status=status.value
            )
            if JiraIssueStatus.DONE == status:
                first_pipeline.zrange(redis_key, start_score, end_score, byscore=True)
            else:
                first_pipeline.smembers(redis_key)
            request_keys_and_info.append((ldap, status))

        first_results = self.retry_utils.get_retry_on_transient(first_pipeline.execute)

        if not should_calculate_story_points:
            for (ldap, status), result in zip(request_keys_and_info, first_results):
                if result:
                    final_result[ldap][status.value].extend(list(result))
                    self.logger.debug(
                        "Redis result for ldap=%s, status=%s: %s", ldap, status, result
                    )

            return final_result
        else:
            story_point_pipeline = self.redis_client.pipeline()

            issue_info_for_story_point_retrieval = []
            for (ldap, status), result in zip(request_keys_and_info, first_results):
                self.logger.debug(
                    "Redis result for ldap=%s, status=%s: %s", ldap, status, result
                )

                if JiraIssueStatus.DONE != status:
                    final_result[ldap][status.value].extend(list(result))
                else:
                    final_result[ldap][status.value].extend(result)

                    for issue_id in result:
                        story_point_pipeline.hget(
                            JIRA_ISSUE_DETAILS_KEY.format(issue_id=issue_id),
                            "story_point",
                        )
                        issue_info_for_story_point_retrieval.append((issue_id, ldap))

            story_point_results = self.retry_utils.get_retry_on_transient(
                story_point_pipeline.execute
            )

            for story_point_data, (issue_id, ldap) in zip(
                story_point_results, issue_info_for_story_point_retrieval
            ):
                if story_point_data:
                    story_point = float(story_point_data)
                    final_result[ldap]["done_story_points_total"] += story_point

                    self.logger.debug(
                        "Added story_point=%s to ldap=%s, total now=%s",
                        story_point,
                        ldap,
                        final_result[ldap]["done_story_points_total"],
                    )

            return dict(final_result)

    def process_get_issue_detail_batch(self, issue_ids: list[str]) -> list[dict]:
        """
        Fetch issue details from Redis and return as a list of dicts.

        Each dict contains 'issue_id' and all fields from the Redis hash.
        Missing fields are filled with None.

        Args:
            issue_ids (list[str]): A list of Jira issue IDs to fetch from Redis.

        Returns:
            list[dict]: A list of dictionaries where each dictionary represents one
                        Jira issue with its metadata. Example:
                        [
                            {"issue_id": "issue-1", "field1": "value1", "field2": "value2"},
                            {"issue_id": "issue-2", "field1": "value1", "field2": "value2"},
                            {"issue_id": "issue-3", "field1": None, "field2": None}
                        ]

        """
        if not issue_ids:
            raise ValueError("issue_ids cannot be empty")

        pipeline = self.redis_client.pipeline()
        for issue_id in issue_ids:
            redis_key = JIRA_ISSUE_DETAILS_KEY.format(issue_id=issue_id)
            pipeline.hgetall(redis_key)

        pipeline_results = self.retry_utils.get_retry_on_transient(pipeline.execute)

        all_fields = {
            field
            for redis_value in pipeline_results
            if redis_value
            for field in redis_value.keys()
        }
        result_list = [
            {
                "issue_id": issue_id,
                **{
                    field: redis_value.get(field) if redis_value else None
                    for field in all_fields
                },
            }
            for issue_id, redis_value in zip(issue_ids, pipeline_results)
        ]

        return result_list
