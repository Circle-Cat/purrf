from unittest import TestCase, main
from unittest.mock import Mock, MagicMock, patch, ANY
from backend.common.constants import (
    JIRA_PROJECTS_KEY,
    JiraIssueStatus,
    JIRA_ISSUE_DETAILS_KEY,
)
from backend.frontend_service.jira_analytics_service import JiraAnalyticsService
from datetime import datetime, timezone


class TestJiraAnalyticsService(TestCase):
    def setUp(self):
        self.mock_logger = Mock()
        self.mock_redis = Mock()
        self.mock_date_time_util = Mock()
        self.mock_ldap_service = Mock()
        self.mock_retry_utils = Mock()

        # Make retry util execute the function directly
        self.mock_retry_utils.get_retry_on_transient.side_effect = (
            lambda func, *args, **kwargs: func(*args, **kwargs)
        )

        self.jira_service = JiraAnalyticsService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            date_time_util=self.mock_date_time_util,
            ldap_service=self.mock_ldap_service,
            retry_utils=self.mock_retry_utils,
        )

        # Common mock data for date/time
        self.start_dt = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.end_dt = datetime(2023, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        self.mock_date_time_util.get_start_end_timestamps.return_value = (
            self.start_dt,
            self.end_dt,
        )
        self.mock_date_time_util.format_datetime_to_int.side_effect = [
            1672531200,
            1675209599,
        ]

    def test_get_all_jira_projects_success(self):
        mock_project_data = {"10503": "Intern Practice", "24998": "Purrf"}
        self.mock_redis.hgetall.return_value = mock_project_data

        result = self.jira_service.get_all_jira_projects()

        self.assertEqual(result, mock_project_data)
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            self.mock_redis.hgetall, JIRA_PROJECTS_KEY
        )

    def test_get_all_jira_projects_empty(self):
        mock_project_data = {}
        self.mock_redis.hgetall.return_value = mock_project_data

        result = self.jira_service.get_all_jira_projects()

        self.assertEqual(result, mock_project_data)
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            self.mock_redis.hgetall, JIRA_PROJECTS_KEY
        )

    def test_get_all_jira_projects_connection_error(self):
        self.mock_retry_utils.get_retry_on_transient.side_effect = ConnectionError(
            "Redis unavailable"
        )

        with self.assertRaises(ConnectionError):
            self.jira_service.get_all_jira_projects()

        self.assertEqual(self.mock_retry_utils.get_retry_on_transient.call_count, 1)

    def test_get_issues_summary_without_done_status(self):
        """Test summary generation for statuses other than DONE."""
        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [
            {"issue-101", "issue-102"},  # user1, in_progress, proj1
            {"issue-103"},  # user1, todo, proj1
        ]

        result = self.jira_service.get_issues_summary(
            status_list=[JiraIssueStatus.IN_PROGRESS, JiraIssueStatus.TODO],
            ldaps=["user1"],
            project_ids=["proj1"],
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.assertEqual(mock_pipeline.smembers.call_count, 2)
        mock_pipeline.zrange.assert_not_called()
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            mock_pipeline.execute
        )

        self.assertIn("user1", result)
        self.assertIn("in_progress", result["user1"])
        self.assertIn("todo", result["user1"])
        self.assertCountEqual(
            result["user1"]["in_progress"], ["issue-101", "issue-102"]
        )
        self.assertCountEqual(result["user1"]["todo"], ["issue-103"])
        self.assertEqual(result["user1"]["done_story_points_total"], 0.0)

    def test_get_issues_summary_with_done_status_and_story_points(self):
        """Test summary generation including DONE status and story point calculation."""
        first_pipeline = MagicMock()
        story_point_pipeline = MagicMock()
        self.mock_redis.pipeline.side_effect = [first_pipeline, story_point_pipeline]

        first_pipeline.execute.return_value = [
            ["done-issue-1", "done-issue-2"],  # user1, done, proj1
            {"inprogress-issue-1"},  # user1, in_progress, proj1
        ]
        story_point_pipeline.execute.return_value = [
            "5.0",  # story point for done-issue-1
            "3.0",  # story point for done-issue-2
        ]

        result = self.jira_service.get_issues_summary(
            status_list=[JiraIssueStatus.DONE, JiraIssueStatus.IN_PROGRESS],
            ldaps=["user1"],
            project_ids=["proj1"],
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.assertEqual(self.mock_redis.pipeline.call_count, 2)
        first_pipeline.zrange.assert_called_once()
        first_pipeline.smembers.assert_called_once()
        self.mock_retry_utils.get_retry_on_transient.assert_any_call(
            first_pipeline.execute
        )

        self.assertEqual(story_point_pipeline.hget.call_count, 2)
        self.mock_retry_utils.get_retry_on_transient.assert_any_call(
            story_point_pipeline.execute
        )

        self.assertIn("user1", result)
        self.assertCountEqual(result["user1"]["done"], ["done-issue-1", "done-issue-2"])
        self.assertCountEqual(result["user1"]["in_progress"], ["inprogress-issue-1"])
        self.assertEqual(result["user1"]["done_story_points_total"], 8.0)

    @patch(
        "backend.frontend_service.jira_analytics_service.JiraAnalyticsService.get_all_jira_projects",
        return_value={"proj1": "Project 1"},
    )
    def test_get_issues_summary_with_defaults(self, mock_get_projects):
        """Test that the method correctly uses defaults for ldaps and project_ids."""
        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.return_value = [
            "intern1",
            "employee1",
        ]
        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline

        mock_pipeline.smembers.return_value = {"issue-1", "issue-2"}

        mock_get_projects.return_value = ["test_project-1"]

        self.jira_service.get_issues_summary(
            status_list=[JiraIssueStatus.IN_PROGRESS, JiraIssueStatus.DONE],
            ldaps=None,
            project_ids=None,
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.assert_called_once()
        mock_get_projects.assert_called_once()

        expected_keys = [
            "jira:ldap:intern1:project:test_project-1:status:done",
            "jira:ldap:employee1:project:test_project-1:status:in_progress",
        ]

        for key in expected_keys:
            if "in_progress" in key:
                mock_pipeline.smembers.assert_any_call(key)
            else:
                mock_pipeline.zrange.assert_any_call(key, ANY, ANY, byscore=True)

    def test_get_issues_summary_with_no_results(self):
        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [set(), set()]

        result = self.jira_service.get_issues_summary(
            status_list=[JiraIssueStatus.IN_PROGRESS, JiraIssueStatus.TODO],
            ldaps=["user1"],
            project_ids=["proj1"],
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.assertEqual(result["user1"]["in_progress"], [])
        self.assertEqual(result["user1"]["todo"], [])
        self.assertEqual(result["user1"]["done_story_points_total"], 0.0)

    def test_get_issues_summary_done_with_missing_story_points(self):
        first_pipeline = MagicMock()
        story_point_pipeline = MagicMock()
        self.mock_redis.pipeline.side_effect = [first_pipeline, story_point_pipeline]

        first_pipeline.execute.return_value = [
            ["done-1", "done-2"],  # both DONE
        ]
        story_point_pipeline.execute.return_value = [
            "4.0",  # valid
            None,  # missing
        ]

        result = self.jira_service.get_issues_summary(
            status_list=[JiraIssueStatus.DONE],
            ldaps=["user1"],
            project_ids=["proj1"],
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.assertEqual(result["user1"]["done_story_points_total"], 4.0)
        self.assertCountEqual(result["user1"]["done"], ["done-1", "done-2"])

    def test_process_get_issue_detail_batch_success(self):
        """Test fetching issue details in batch successfully."""
        issue_ids = ["issue-1", "issue-2"]
        pipeline_results = [
            {"summary": "First issue", "status": "Done"},
            {"summary": "Second issue", "status": "In Progress"},
        ]
        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = pipeline_results

        result = self.jira_service.process_get_issue_detail_batch(issue_ids)

        self.assertEqual(len(result), 2)
        self.assertCountEqual(
            result,
            [
                {
                    "issue_id": "issue-1",
                    "summary": "First issue",
                    "status": "Done",
                },
                {
                    "issue_id": "issue-2",
                    "summary": "Second issue",
                    "status": "In Progress",
                },
            ],
        )
        self.assertEqual(mock_pipeline.hgetall.call_count, 2)
        mock_pipeline.hgetall.assert_any_call(
            JIRA_ISSUE_DETAILS_KEY.format(issue_id="issue-1")
        )
        mock_pipeline.hgetall.assert_any_call(
            JIRA_ISSUE_DETAILS_KEY.format(issue_id="issue-2")
        )

    def test_process_get_issue_detail_batch_with_missing_details(self):
        """Test batch fetch where some issue details are missing."""
        issue_ids = ["issue-1", "issue-2", "issue-3"]
        pipeline_results = [
            {"summary": "First issue", "story_point": "5"},
            None,
            {"summary": "Third issue", "status": "To Do"},
        ]
        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = pipeline_results

        result = self.jira_service.process_get_issue_detail_batch(issue_ids)

        self.assertEqual(len(result), 3)
        self.assertCountEqual(
            result,
            [
                {
                    "issue_id": "issue-1",
                    "summary": "First issue",
                    "story_point": "5",
                    "status": None,
                },
                {
                    "issue_id": "issue-2",
                    "summary": None,
                    "story_point": None,
                    "status": None,
                },
                {
                    "issue_id": "issue-3",
                    "summary": "Third issue",
                    "story_point": None,
                    "status": "To Do",
                },
            ],
        )

    def test_process_get_issue_detail_batch_empty_input(self):
        """Test batch fetch with an empty list of issue IDs."""
        with self.assertRaises(ValueError):
            self.jira_service.process_get_issue_detail_batch([])

        self.mock_redis.pipeline.assert_not_called()
        self.mock_redis.pipeline.return_value.hgetall.assert_not_called()
        self.mock_redis.pipeline.return_value.execute.assert_not_called()


if __name__ == "__main__":
    main()
