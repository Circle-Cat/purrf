import unittest
from unittest.mock import MagicMock, call, patch

from backend.service.jira_search_service import JiraSearchService
from backend.common.constants import (
    JIRA_MAX_RESULTS_DEFAULT,
    JIRA_ISSUE_REQUIRED_FIELDS,
)


class TestJiraSearchService(unittest.TestCase):
    MOCK_MAX_RESULTS = 2

    def setUp(self):
        self.logger = MagicMock()
        self.jira_client = MagicMock()
        self.retry_utils = MagicMock()
        self.service = JiraSearchService(
            logger=self.logger,
            jira_client=self.jira_client,
            retry_utils=self.retry_utils,
        )
        self.required_fields = JIRA_ISSUE_REQUIRED_FIELDS

    def test_fetch_issue_by_issue_id_success(self):
        self.retry_utils.get_retry_on_transient.return_value = []

        self.service.fetch_issue_by_issue_id(issue_id="123")

        self.retry_utils.get_retry_on_transient.assert_called_once_with(
            self.jira_client.issue, id="123", fields="assignee"
        )

    def test_fetch_issue_by_issue_id_with_illegal_id(self):
        with self.assertRaises(ValueError):
            self.service.fetch_issue_by_issue_id(issue_id="")

        with self.assertRaises(ValueError):
            self.service.fetch_issue_by_issue_id(issue_id=None)

    @patch(
        "backend.service.jira_search_service.JIRA_MAX_RESULTS_DEFAULT", MOCK_MAX_RESULTS
    )
    def test_fetch_assigned_issues_paginated_multiple_pages(self):
        mock_issues_page1 = [MagicMock() for _ in range(self.MOCK_MAX_RESULTS)]
        mock_issues_page2 = [MagicMock() for _ in range(self.MOCK_MAX_RESULTS)]
        mock_issues_page3 = [MagicMock()]
        self.retry_utils.get_retry_on_transient.side_effect = [
            mock_issues_page1,
            mock_issues_page2,
            mock_issues_page3,
        ]
        expected_jql = "assignee IS NOT EMPTY"

        result_generator = self.service.fetch_assigned_issues_paginated()
        all_issues = []
        for page in result_generator:
            all_issues.extend(page)

        self.assertEqual(len(all_issues), 5)
        self.assertEqual(self.retry_utils.get_retry_on_transient.call_count, 3)

        expected_calls = [
            call(
                self.jira_client.search_issues,
                jql_str=expected_jql,
                startAt=0,
                maxResults=self.MOCK_MAX_RESULTS,
                fields=self.required_fields,
            ),
            call(
                self.jira_client.search_issues,
                jql_str=expected_jql,
                startAt=self.MOCK_MAX_RESULTS,
                maxResults=self.MOCK_MAX_RESULTS,
                fields=self.required_fields,
            ),
            call(
                self.jira_client.search_issues,
                jql_str=expected_jql,
                startAt=self.MOCK_MAX_RESULTS * 2,
                maxResults=self.MOCK_MAX_RESULTS,
                fields=self.required_fields,
            ),
        ]
        self.retry_utils.get_retry_on_transient.assert_has_calls(expected_calls)

    def test_fetch_assigned_issues_paginated_no_results(self):
        self.retry_utils.get_retry_on_transient.return_value = []
        expected_jql = "assignee IS NOT EMPTY"

        result_generator = self.service.fetch_assigned_issues_paginated()
        all_issues = list(result_generator)

        self.assertEqual(len(all_issues), 1)
        self.assertEqual(len(all_issues[0]), 0)

        self.retry_utils.get_retry_on_transient.assert_called_once_with(
            self.jira_client.search_issues,
            jql_str=expected_jql,
            startAt=0,
            maxResults=JIRA_MAX_RESULTS_DEFAULT,
            fields=self.required_fields,
        )

    @patch(
        "backend.service.jira_search_service.JIRA_MAX_RESULTS_DEFAULT", MOCK_MAX_RESULTS
    )
    def test_fetch_issues_updated_within_hours_paginated_success(self):
        hours = 24
        mock_issues_page1 = [MagicMock() for _ in range(self.MOCK_MAX_RESULTS)]
        mock_issues_page2 = [MagicMock()]
        self.retry_utils.get_retry_on_transient.side_effect = [
            mock_issues_page1,
            mock_issues_page2,
        ]
        expected_jql = (
            f"(updated >= -{hours}h OR created >= -{hours}h) ORDER BY created DESC"
        )

        result_generator = self.service.fetch_issues_updated_within_hours_paginated(
            hours=hours
        )
        all_issues = []
        for page in result_generator:
            all_issues.extend(page)

        self.assertEqual(len(all_issues), 3)
        self.assertEqual(self.retry_utils.get_retry_on_transient.call_count, 2)
        expected_calls = [
            call(
                self.jira_client.search_issues,
                jql_str=expected_jql,
                startAt=0,
                maxResults=self.MOCK_MAX_RESULTS,
                fields=self.required_fields,
            ),
            call(
                self.jira_client.search_issues,
                jql_str=expected_jql,
                startAt=self.MOCK_MAX_RESULTS,
                maxResults=self.MOCK_MAX_RESULTS,
                fields=self.required_fields,
            ),
        ]
        self.retry_utils.get_retry_on_transient.assert_has_calls(expected_calls)

    def test_fetch_issues_updated_within_hours_paginated_invalid_hours(self):
        with self.assertRaises(ValueError):
            list(self.service.fetch_issues_updated_within_hours_paginated(hours=0))

        with self.assertRaises(ValueError):
            list(self.service.fetch_issues_updated_within_hours_paginated(hours=-1))

        with self.assertRaises(ValueError):
            list(self.service.fetch_issues_updated_within_hours_paginated(hours=None))

        self.retry_utils.get_retry_on_transient.assert_not_called()


if __name__ == "__main__":
    unittest.main()
