from unittest import TestCase, main
from unittest.mock import MagicMock, patch
from backend.historical_data.jira_history_sync_service import JiraHistorySyncService
from backend.common.constants import (
    JiraIssueStatus,
    JIRA_ISSUE_DETAILS_KEY,
    JIRA_STORY_POINT_FIELD,
    JIRA_LDAP_PROJECT_STATUS_INDEX_KEY,
    JIRA_EXCLUDED_STATUS_ID,
)


class TestJiraHistorySyncService(TestCase):
    """Test JiraHistorySyncService functionality."""

    def setUp(self):
        """Set up the test environment before each test."""
        self.mock_logger = MagicMock()
        self.mock_jira_client = MagicMock()
        self.mock_redis_client = MagicMock()
        self.mock_jira_search_service = MagicMock()
        self.mock_date_time_util = MagicMock()
        self.mock_retry_utils = MagicMock()

        self.mock_retry_utils.get_retry_on_transient.side_effect = (
            lambda func, *args, **kwargs: func(*args, **kwargs)
        )

        self.service = JiraHistorySyncService(
            logger=self.mock_logger,
            jira_client=self.mock_jira_client,
            redis_client=self.mock_redis_client,
            jira_search_service=self.mock_jira_search_service,
            date_time_util=self.mock_date_time_util,
            retry_utils=self.mock_retry_utils,
        )

        # Common mock data
        self.finish_date = 1678886400  # Example timestamp: 2023-03-15 00:00:00 UTC
        self.mock_date_time_util.format_datetime_str_to_int.return_value = (
            self.finish_date
        )

        self.mock_issue_1_id = "10001"
        self.mock_issue_1_key = "PROJ-1"
        self.mock_issue_1_project_id = "100"
        self.mock_issue_1_assignee_name = "johndoe"
        self.mock_issue_1_summary = "Test Issue 1"
        self.mock_issue_1_story_point = 5.0

        # Mock Jira Issue object for a DONE issue
        self.mock_issue_1_raw_data = {
            "id": self.mock_issue_1_id,
            "key": self.mock_issue_1_key,
            "fields": {
                "project": {"id": self.mock_issue_1_project_id},
                "assignee": {"name": self.mock_issue_1_assignee_name},
                "status": {"id": "6", "name": "Done"},  # DONE status
                "summary": self.mock_issue_1_summary,
                JIRA_STORY_POINT_FIELD: self.mock_issue_1_story_point,
                "resolutiondate": "2023-03-15T10:00:00.000+0000",
                "updated": "2023-03-15T09:00:00.000+0000",
                "created": "2023-03-10T08:00:00.000+0000",
            },
        }
        self.mock_issue_1 = MagicMock()
        self.mock_issue_1.raw = self.mock_issue_1_raw_data

        self.expected_detail_info_done = {
            "issue_key": self.mock_issue_1_key,
            "issue_title": self.mock_issue_1_summary,
            "project_id": self.mock_issue_1_project_id,
            "story_point": self.mock_issue_1_story_point,
            "issue_status": JiraIssueStatus.DONE.value,
            "ldap": self.mock_issue_1_assignee_name,
            "finish_date": self.finish_date,
        }

        # Mock issue for non-DONE status
        self.mock_issue_2_id = "10002"
        self.mock_issue_2_key = "PROJ-2"
        self.mock_issue_2_project_id = "100"
        self.mock_issue_2_assignee_name = "janedoe"
        self.mock_issue_2_summary = "Test Issue 2"
        self.mock_issue_2_story_point = 8.0
        self.mock_issue_2_raw_data = {
            "id": self.mock_issue_2_id,
            "key": self.mock_issue_2_key,
            "fields": {
                "project": {"id": self.mock_issue_2_project_id},
                "assignee": {"name": self.mock_issue_2_assignee_name},
                "status": {"id": "10305", "name": "In Progress"},  # IN_PROGRESS status
                "summary": self.mock_issue_2_summary,
                JIRA_STORY_POINT_FIELD: self.mock_issue_2_story_point,
                "updated": "2023-03-14T09:00:00.000+0000",
                "created": "2023-03-09T08:00:00.000+0000",
            },
        }
        self.mock_issue_2 = MagicMock()
        self.mock_issue_2.raw = self.mock_issue_2_raw_data

        self.expected_detail_info_in_progress = {
            "issue_key": self.mock_issue_2_key,
            "issue_title": self.mock_issue_2_summary,
            "project_id": self.mock_issue_2_project_id,
            "story_point": self.mock_issue_2_story_point,
            "issue_status": JiraIssueStatus.IN_PROGRESS.value,
            "ldap": self.mock_issue_2_assignee_name,
        }

    def test_sync_success(self):
        """Should fetch projects and store them in Redis successfully."""
        mock_project1 = MagicMock()
        mock_project1.id = "10001"
        mock_project1.name = "Project Alpha"

        mock_project2 = MagicMock()
        mock_project2.id = "10002"
        mock_project2.name = "Project Beta"

        self.mock_jira_client.projects.return_value = [mock_project1, mock_project2]

        with patch(
            "backend.historical_data.jira_history_sync_service.JIRA_PROJECTS_KEY",
            "mock:project:key",
        ):
            result = self.service.sync_jira_projects_id_and_name_mapping()

        expected = {"10001": "Project Alpha", "10002": "Project Beta"}
        self.assertEqual(result, 2)

        self.mock_jira_client.projects.assert_called_once()
        self.mock_redis_client.delete.assert_called_once_with("mock:project:key")
        self.mock_redis_client.hset.assert_called_once_with(
            "mock:project:key", mapping=expected
        )

    def test_sync_no_projects_error(self):
        """Should raise RuntimeError when no projects are returned."""
        self.mock_jira_client.projects.return_value = []

        with patch(
            "backend.historical_data.jira_history_sync_service.JIRA_PROJECTS_KEY",
            "mock:project:key",
        ):
            result = self.service.sync_jira_projects_id_and_name_mapping()

        self.assertEqual(result, 0)
        self.mock_redis_client.delete.assert_not_called()
        self.mock_redis_client.hset.assert_not_called()
        self.mock_logger.error.assert_called_once_with("No projects found in Jira")

    def test_init_none_clients_or_logger(self):
        """Should raise ValueError if logger, jira_client or redis_client is None."""
        with self.assertRaises(ValueError):
            JiraHistorySyncService(
                logger=None,
                jira_client=self.mock_jira_client,
                redis_client=self.mock_redis_client,
                jira_search_service=self.mock_jira_search_service,
                date_time_util=self.mock_date_time_util,
                retry_utils=self.mock_retry_utils,
            )

        with self.assertRaises(ValueError):
            JiraHistorySyncService(
                logger=self.mock_logger,
                jira_client=None,
                redis_client=self.mock_redis_client,
                jira_search_service=self.mock_jira_search_service,
                date_time_util=self.mock_date_time_util,
                retry_utils=self.mock_retry_utils,
            )

        with self.assertRaises(ValueError):
            JiraHistorySyncService(
                logger=self.mock_logger,
                jira_client=self.mock_jira_client,
                redis_client=None,
                jira_search_service=self.mock_jira_search_service,
                date_time_util=self.mock_date_time_util,
                retry_utils=self.mock_retry_utils,
            )

    def test_backfill_all_jira_issues_single_batch(self):
        """Should fetch and store all assigned issues from a single batch."""
        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline
        self.mock_jira_search_service.fetch_assigned_issues_paginated.return_value = [
            [self.mock_issue_1]
        ]
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda func: func
        mock_pipeline.execute.return_value = None

        result = self.service.backfill_all_jira_issues()

        self.assertEqual(result, 1)
        self.mock_jira_search_service.fetch_assigned_issues_paginated.assert_called_once()
        mock_pipeline.hset.assert_called_once_with(
            JIRA_ISSUE_DETAILS_KEY.format(issue_id=self.mock_issue_1_id),
            mapping=self.expected_detail_info_done,
        )
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            mock_pipeline.execute
        )

    def test_preprocess_issue_status_valid_status(self):
        """Should return correct JiraIssueStatus for a valid status ID."""
        status_info = {"id": "10000", "name": "To Do"}
        issue_key = "TEST-123"
        result = self.service._preprocess_issue_status(status_info, issue_key)
        self.assertEqual(result, JiraIssueStatus.TODO)

    def test_preprocess_issue_status_empty_info(self):
        """Should return None and log debug for empty status_info."""
        status_info = {}
        issue_key = "TEST-123"
        result = self.service._preprocess_issue_status(status_info, issue_key)
        self.assertIsNone(result)

    def test_preprocess_issue_status_excluded_status(self):
        """Should return None and log debug for an excluded status ID."""
        status_info = {"id": JIRA_EXCLUDED_STATUS_ID, "name": "Obsolete"}
        issue_key = "TEST-123"
        result = self.service._preprocess_issue_status(status_info, issue_key)
        self.assertIsNone(result)

    def test_preprocess_issue_status_unknown_status(self):
        """Should return None and log debug for an unknown status ID."""
        status_info = {"id": "999999", "name": "New Status"}
        issue_key = "TEST-123"
        result = self.service._preprocess_issue_status(status_info, issue_key)
        self.assertIsNone(result)

    def test_preprocess_issue_status_missing_id(self):
        """Should return None and log debug if status_info is missing 'id'."""
        status_info = {"name": "Some Status"}
        issue_key = "TEST-123"
        result = self.service._preprocess_issue_status(status_info, issue_key)
        self.assertIsNone(result)

    def test_get_finish_date_for_done_status_resolutiondate(self):
        """Should use 'resolutiondate' if available and valid."""
        issue_key = "PROJ-1"
        issue_id = "10001"
        fields = {
            "resolutiondate": "2023-01-01T10:00:00.000+0000",
            "updated": "2023-01-02T10:00:00.000+0000",
            "created": "2023-01-03T10:00:00.000+0000",
        }
        expected_timestamp = 1672560000

        self.mock_date_time_util.format_datetime_str_to_int.side_effect = [
            expected_timestamp,
            None,
            None,
        ]

        result = self.service._get_finish_date_for_done_status(
            issue_key, issue_id, fields
        )
        self.assertEqual(result, expected_timestamp)
        self.mock_date_time_util.format_datetime_str_to_int.assert_called_once_with(
            "2023-01-01T10:00:00.000+0000"
        )
        self.mock_logger.debug.assert_not_called()

    def test_get_finish_date_for_done_status_fallback_updated(self):
        """Should fallback to 'updated' if 'resolutiondate' is missing/invalid."""
        issue_key = "PROJ-1"
        issue_id = "10001"
        fields = {
            "resolutiondate": "invalid-date",
            "updated": "2023-01-02T10:00:00.000+0000",
            "created": "2023-01-03T10:00:00.000+0000",
        }

        self.mock_date_time_util.format_datetime_str_to_int.side_effect = [
            None,
            self.finish_date,
        ]

        result = self.service._get_finish_date_for_done_status(
            issue_key, issue_id, fields
        )
        self.assertEqual(result, self.finish_date)
        self.mock_date_time_util.format_datetime_str_to_int.assert_any_call(
            "invalid-date"
        )
        self.mock_date_time_util.format_datetime_str_to_int.assert_any_call(
            "2023-01-02T10:00:00.000+0000"
        )
        self.mock_logger.debug.assert_called_once_with(
            "Issue '%s' (ID: %s) has DONE status but no valid 'resolutiondate'. Using '%s' date instead.",
            issue_key,
            issue_id,
            "updated",
        )

    def test_get_finish_date_for_done_status_fallback_created(self):
        """Should fallback to 'created' if 'resolutiondate' and 'updated' are missing/invalid."""
        issue_key = "PROJ-1"
        issue_id = "10001"
        fields = {
            "resolutiondate": None,
            "updated": "",
            "created": "2023-01-03T10:00:00.000+0000",
        }
        self.mock_date_time_util.format_datetime_str_to_int.return_value = (
            self.finish_date
        )

        result = self.service._get_finish_date_for_done_status(
            issue_key, issue_id, fields
        )
        self.assertEqual(result, self.finish_date)

    def test_get_finish_date_for_done_status_no_dates(self):
        """Should return None if no valid date fields are found."""
        issue_key = "PROJ-1"
        issue_id = "10001"
        fields = {
            "resolutiondate": None,
            "updated": None,
            "created": None,
        }
        self.mock_date_time_util.format_datetime_str_to_int.return_value = None

        result = self.service._get_finish_date_for_done_status(
            issue_key, issue_id, fields
        )
        self.assertIsNone(result)
        self.mock_date_time_util.format_datetime_str_to_int.assert_not_called()

    def test_queue_issues_in_redis_pipeline_done_issue(self):
        """Should queue a DONE issue with ZADD and HSET commands."""
        mock_pipeline = MagicMock()
        issues = [self.mock_issue_1]

        result = self.service._queue_issues_in_redis_pipeline(issues, mock_pipeline)

        self.assertEqual(result, 1)
        expected_set_key = JIRA_ISSUE_DETAILS_KEY.format(issue_id=self.mock_issue_1_id)
        mock_pipeline.hset.assert_called_once_with(
            expected_set_key,
            mapping=self.expected_detail_info_done,
        )
        expected_zadd_key = JIRA_LDAP_PROJECT_STATUS_INDEX_KEY.format(
            ldap=self.mock_issue_1_assignee_name,
            project_id=self.mock_issue_1_project_id,
            status=JiraIssueStatus.DONE.value,
        )
        mock_pipeline.zadd.assert_called_once_with(
            expected_zadd_key,
            {self.mock_issue_1_id: self.finish_date},
        )
        mock_pipeline.sadd.assert_not_called()

    def test_queue_issues_in_redis_pipeline_non_done_issue(self):
        """Should queue a non-DONE issue with SADD and HSET commands."""
        mock_pipeline = MagicMock()
        issues = [self.mock_issue_2]

        result = self.service._queue_issues_in_redis_pipeline(issues, mock_pipeline)

        self.assertEqual(result, 1)
        expected_set_key = JIRA_ISSUE_DETAILS_KEY.format(issue_id=self.mock_issue_2_id)
        mock_pipeline.hset.assert_called_once_with(
            expected_set_key,
            mapping=self.expected_detail_info_in_progress,
        )
        expected_sadd_key = JIRA_LDAP_PROJECT_STATUS_INDEX_KEY.format(
            ldap=self.mock_issue_2_assignee_name,
            project_id=self.mock_issue_2_project_id,
            status=JiraIssueStatus.IN_PROGRESS.value,
        )
        mock_pipeline.sadd.assert_called_once_with(
            expected_sadd_key,
            self.mock_issue_2_id,
        )
        mock_pipeline.zadd.assert_not_called()

    def test_queue_issues_in_redis_pipeline_skip_missing_id(self):
        """Should skip issues missing 'id'."""
        mock_pipeline = MagicMock()
        issue_with_missing_id = MagicMock()
        issue_with_missing_id.raw = {
            "key": "PROJ-INVALID",
            "fields": {
                "project": {"id": "100"},
                "assignee": {"name": "testuser"},
                "status": {"id": "10000", "name": "To Do"},
            },
        }
        issues = [issue_with_missing_id]

        result = self.service._queue_issues_in_redis_pipeline(issues, mock_pipeline)

        self.assertEqual(result, 0)
        mock_pipeline.hset.assert_not_called()
        mock_pipeline.zadd.assert_not_called()
        mock_pipeline.sadd.assert_not_called()

    def test_queue_issues_in_redis_pipeline_skip_missing_key(self):
        """Should skip issues missing 'key'."""
        mock_pipeline = MagicMock()
        issue_with_missing_key = MagicMock()
        issue_with_missing_key.raw = {
            "id": "10003",
            "fields": {
                "project": {"id": "100"},
                "assignee": {"name": "testuser"},
                "status": {"id": "10000", "name": "To Do"},
            },
        }
        issues = [issue_with_missing_key]

        result = self.service._queue_issues_in_redis_pipeline(issues, mock_pipeline)

        self.assertEqual(result, 0)
        mock_pipeline.hset.assert_not_called()
        mock_pipeline.zadd.assert_not_called()
        mock_pipeline.sadd.assert_not_called()

    def test_queue_issues_in_redis_pipeline_skip_missing_project_id(self):
        """Should skip issues missing 'project_id'."""
        mock_pipeline = MagicMock()
        issue_with_missing_project_id = MagicMock()
        issue_with_missing_project_id.raw = {
            "id": "10003",
            "key": "PROJ-3",
            "fields": {
                "project": {},
                "assignee": {"name": "testuser"},
                "status": {"id": "10000", "name": "To Do"},
            },
        }
        issues = [issue_with_missing_project_id]

        result = self.service._queue_issues_in_redis_pipeline(issues, mock_pipeline)

        self.assertEqual(result, 0)
        mock_pipeline.hset.assert_not_called()
        mock_pipeline.zadd.assert_not_called()
        mock_pipeline.sadd.assert_not_called()

    def test_queue_issues_in_redis_pipeline_skip_missing_assignee(self):
        """Should skip issues with no assignee."""
        mock_pipeline = MagicMock()
        issue_no_assignee = MagicMock()
        issue_no_assignee.raw = {
            "id": "10003",
            "key": "PROJ-3",
            "fields": {
                "project": {"id": "100"},
                "assignee": None,
                "status": {"id": "10000", "name": "To Do"},
            },
        }
        issues = [issue_no_assignee]

        result = self.service._queue_issues_in_redis_pipeline(issues, mock_pipeline)

        self.assertEqual(result, 0)
        mock_pipeline.hset.assert_not_called()
        mock_pipeline.zadd.assert_not_called()
        mock_pipeline.sadd.assert_not_called()

    def test_queue_issues_in_redis_pipeline_skip_excluded_status(self):
        """Should skip issues with an excluded status."""
        mock_pipeline = MagicMock()
        issue_excluded_status = MagicMock()
        issue_excluded_status.raw = {
            "id": "10003",
            "key": "PROJ-3",
            "fields": {
                "project": {"id": "100"},
                "assignee": {"name": "testuser"},
                "status": {"id": JIRA_EXCLUDED_STATUS_ID, "name": "Obsolete"},
            },
        }
        issues = [issue_excluded_status]

        result = self.service._queue_issues_in_redis_pipeline(issues, mock_pipeline)

        self.assertEqual(result, 0)
        mock_pipeline.hset.assert_not_called()
        mock_pipeline.zadd.assert_not_called()
        mock_pipeline.sadd.assert_not_called()

    def test_queue_issues_in_redis_pipeline_skip_unknown_status(self):
        """Should skip issues with an unknown status."""
        mock_pipeline = MagicMock()
        issue_unknown_status = MagicMock()
        issue_unknown_status.raw = {
            "id": "10003",
            "key": "PROJ-3",
            "fields": {
                "project": {"id": "100"},
                "assignee": {"name": "testuser"},
                "status": {"id": "999999", "name": "Unknown"},
            },
        }
        issues = [issue_unknown_status]

        result = self.service._queue_issues_in_redis_pipeline(issues, mock_pipeline)

        self.assertEqual(result, 0)
        mock_pipeline.hset.assert_not_called()
        mock_pipeline.zadd.assert_not_called()
        mock_pipeline.sadd.assert_not_called()

    def test_backfill_all_jira_issues_multiple_batches(self):
        """Should process multiple batches of issues correctly."""
        mock_pipeline_1 = MagicMock()
        mock_pipeline_2 = MagicMock()
        self.mock_redis_client.pipeline.side_effect = [mock_pipeline_1, mock_pipeline_2]

        self.mock_date_time_util.format_datetime_str_to_int.return_value = (
            self.finish_date
        )

        issues_batch_1 = [self.mock_issue_1, self.mock_issue_2]

        mock_issue_3_id = "10003"
        mock_issue_3_key = "PROJ-3"
        mock_issue_3_summary = "Test Issue 3"
        mock_issue_3_story_point = 3.0
        mock_issue_3_raw_data = {
            "id": mock_issue_3_id,
            "key": mock_issue_3_key,
            "fields": {
                "project": {"id": "101"},
                "assignee": {"name": "user3"},
                "status": {"id": "6", "name": "Done"},
                "summary": mock_issue_3_summary,
                "resolutiondate": "2023-03-16T10:00:00.000+0000",
                JIRA_STORY_POINT_FIELD: mock_issue_3_story_point,
            },
        }
        mock_issue_3 = MagicMock()
        mock_issue_3.raw = mock_issue_3_raw_data
        issues_batch_2 = [mock_issue_3]

        self.mock_jira_search_service.fetch_assigned_issues_paginated.return_value = [
            issues_batch_1,
            issues_batch_2,
        ]

        result = self.service.backfill_all_jira_issues()

        self.assertEqual(result, 3)

        self.mock_jira_search_service.fetch_assigned_issues_paginated.assert_called_once()
        self.assertEqual(self.mock_redis_client.pipeline.call_count, 2)

        mock_pipeline_1.hset.assert_any_call(
            JIRA_ISSUE_DETAILS_KEY.format(issue_id=self.mock_issue_1_id),
            mapping=self.expected_detail_info_done,
        )
        mock_pipeline_1.hset.assert_any_call(
            JIRA_ISSUE_DETAILS_KEY.format(issue_id=self.mock_issue_2_id),
            mapping=self.expected_detail_info_in_progress,
        )
        self.assertEqual(mock_pipeline_1.zadd.call_count, 1)
        self.assertEqual(mock_pipeline_1.sadd.call_count, 1)
        self.mock_retry_utils.get_retry_on_transient.assert_any_call(
            mock_pipeline_1.execute
        )

        expected_detail_info_mock_issue_3 = {
            "issue_key": mock_issue_3_key,
            "issue_title": mock_issue_3_summary,
            "project_id": mock_issue_3_raw_data["fields"]["project"]["id"],
            "story_point": mock_issue_3_story_point,
            "issue_status": JiraIssueStatus.DONE.value,
            "ldap": mock_issue_3_raw_data["fields"]["assignee"]["name"],
            "finish_date": self.finish_date,
        }
        mock_pipeline_2.hset.assert_any_call(
            JIRA_ISSUE_DETAILS_KEY.format(issue_id=mock_issue_3_id),
            mapping=expected_detail_info_mock_issue_3,
        )
        self.assertEqual(mock_pipeline_2.zadd.call_count, 1)
        self.assertEqual(mock_pipeline_2.sadd.call_count, 0)
        self.mock_retry_utils.get_retry_on_transient.assert_any_call(
            mock_pipeline_2.execute
        )


if __name__ == "__main__":
    main()
