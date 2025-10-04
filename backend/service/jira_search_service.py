import logging
from typing import Generator

from jira import JIRA
from jira.resources import Issue

from backend.utils.retry_utils import RetryUtils
from backend.common.constants import (
    JIRA_MAX_RESULTS_DEFAULT,
    JIRA_ISSUE_REQUIRED_FIELDS,
)


class JiraSearchService:
    """
    A service class that encapsulates interactions with the JIRA REST API.

    Args:
        logger (logging.Logger): Logger instance for logging info and errors.
        jira_client (JIRA): JIRA client instance.
        retry_utils (RetryUtils): Utility class for handling retries.
    """

    def __init__(
        self,
        logger: logging.Logger,
        jira_client: JIRA,
        retry_utils: RetryUtils,
    ):
        """Initialize the JiraSearchService."""
        self.logger = logger
        self.jira_client = jira_client
        self.retry_utils = retry_utils

    def _fetch_issues_by_jql_paginated(
        self, jql_query: str
    ) -> Generator[list[Issue], None, None]:
        """Fetches all issues from Jira for a given JQL query, handling pagination.

        This method uses a generator to yield issues in batches, which is more
        memory-efficient than fetching all issues at once, especially for large
        result sets. It repeatedly calls the Jira API, incrementing the starting
        index (`startAt`) until all issues have been retrieved.

        Args:
            jql_query (str): The JQL (Jira Query Language) string to filter issues.

        Yields:
            Generator[list[Issue], None, None]: A generator that yields lists of
            `Issue` objects. Each list represents a batch of issues.
        """
        if not jql_query:
            raise ValueError("JQL query must be provided.")

        start_at = 0
        batch_size = JIRA_MAX_RESULTS_DEFAULT
        self.logger.debug("Starting Jira issue fetch with JQL: %s", jql_query)

        while True:
            issues = self.retry_utils.get_retry_on_transient(
                self.jira_client.search_issues,
                jql_str=jql_query,
                startAt=start_at,
                maxResults=batch_size,
                fields=JIRA_ISSUE_REQUIRED_FIELDS,
            )

            self.logger.info(
                "Fetched %d issues starting at index %d", len(issues), start_at
            )
            yield issues

            if len(issues) < batch_size:
                self.logger.info("All issues fetched, stopping pagination")
                break

            start_at += batch_size

    def fetch_assigned_issues_paginated(self) -> Generator[list[Issue], None, None]:
        """
        Fetch Jira issues that have an assignee in a paginated manner.

        Constructs a JQL query to find issues where the assignee is not empty.
        Retrieves issues in batches to efficiently handle large result sets.

        Yields:
            Generator[list[Issue], None, None]: Lists of Jira Issue objects in batches.
        """

        jql_query = "assignee IS NOT EMPTY"
        yield from self._fetch_issues_by_jql_paginated(jql_query)

    def fetch_issues_updated_within_hours_paginated(
        self, hours: int
    ) -> Generator[list[Issue], None, None]:
        """
        Fetch Jira issues updated or created within the past `hours` hours, paginated.

        Args:
            hours (int): Only issues updated or created within the last `hours` hours will be fetched.

        Yields:
            Generator[list[Issue], None, None]: Lists of Jira Issue objects in batches.
        """
        if not hours or hours <= 0:
            raise ValueError("Hours must be a positive integer.")

        jql_query = (
            f"(updated >= -{hours}h OR created >= -{hours}h) ORDER BY created DESC"
        )
        yield from self._fetch_issues_by_jql_paginated(jql_query)

    def fetch_issue_by_issue_id(self, issue_id: str) -> Issue:
        """
        Fetches issue from Jira for a given issue ID.
        Currently, this method only retrieves the `assignee` field of the issue.
        If you need additional fields, you can modify the `fields` parameter

        Args:
            issue_id (str): The issue_id string to filter issue.
        """
        if not issue_id:
            raise ValueError("issue_id must be provided.")

        issue = self.retry_utils.get_retry_on_transient(
            self.jira_client.issue, id=issue_id, fields="assignee"
        )
        return issue
