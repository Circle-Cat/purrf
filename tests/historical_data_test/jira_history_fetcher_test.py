from unittest import TestCase, main
from unittest.mock import patch, MagicMock, call, ANY
from src.historical_data.jira_history_fetcher import (
    format_resolution_date,
    store_issues_in_redis,
    fetch_incremental_issues,
    group_incremental_issues_by_ldap,
    process_incremental_issues_data,
    update_incremental_issue_indexes,
    remove_updated_issue_previous_indexes,
    process_update_jira_issues,
    fetch_issues_with_metadata,
    fetch_and_store_issues_for_ldap,
    process_backfill_jira_issues,
    fetch_jira_projects,
    store_jira_projects_in_redis,
    process_sync_jira_projects,
)
from src.common.constants import JiraIssueStatus


class TestFormatResolutionDate(TestCase):
    """Test date formatting functionality."""

    def test_converts_valid_iso_date_to_integer(self):
        """Should convert ISO date string to YYYYMMDD integer format."""
        result = format_resolution_date("2023-12-25T10:30:00.000+0000")
        self.assertEqual(result, 20231225)

        result = format_resolution_date("2024-01-01T23:59:59.999+0000")
        self.assertEqual(result, 20240101)

    def test_returns_none_for_invalid_input(self):
        """Should return None for invalid date formats or None input."""
        invalid_inputs = ["invalid-date", "", "2023-13-45", None]
        for invalid_input in invalid_inputs:
            with self.subTest(input=invalid_input):
                result = format_resolution_date(invalid_input)
                self.assertIsNone(result)


class TestStoreIssuesInRedis(TestCase):
    """Test Redis storage functionality."""

    def setUp(self):
        """Set up test data."""
        self.sample_issues = [
            {
                "issue_id": "12345",
                "redis_data": {
                    "issue_key": "PROJ-123",
                    "issue_title": "Test Issue",
                    "project_id": "10001",
                    "story_point": 5,
                    "issue_status": JiraIssueStatus.TODO,
                    "ldap": "test_user",
                    "finish_date": None,
                },
            }
        ]

    def test_stores_issues_successfully(self):
        """Should store issues and return success count."""
        mock_pipeline = MagicMock()

        result = store_issues_in_redis(self.sample_issues, mock_pipeline)

        self.assertEqual(result, 1)

        # Verify that the pipeline commands were executed
        self.assertTrue(mock_pipeline.json.called)
        self.assertTrue(mock_pipeline.json().set.called)

    def test_handles_empty_input_gracefully(self):
        """Should handle empty issue list without errors."""
        mock_pipeline = MagicMock()

        result = store_issues_in_redis([], mock_pipeline)

        self.assertEqual(result, 0)

        # Verify that no pipeline commands were executed for empty input
        self.assertFalse(mock_pipeline.json.called)


class TestFetchIncrementalIssues(TestCase):
    """Test incremental issue fetching functionality."""

    def test_constructs_correct_jql_and_fetches_issues(self):
        """Should construct proper JQL query and fetch issues."""
        mock_jira_client = MagicMock()
        mock_jira_client.search_issues.return_value = [MagicMock(), MagicMock()]

        result = fetch_incremental_issues(24, mock_jira_client)

        # Verify JQL contains required filters
        call_args = mock_jira_client.search_issues.call_args[0]
        jql = call_args[0]
        self.assertIn("-24h", jql)
        self.assertIn("assignee IS NOT EMPTY", jql)
        self.assertEqual(len(result), 2)

    def test_raises_error_for_none_client(self):
        """Should raise ValueError when jira_client is None."""
        with self.assertRaises(ValueError):
            fetch_incremental_issues(24, None)


class TestGroupIncrementalIssuesByLdap(TestCase):
    """Test issue grouping by LDAP functionality."""

    def test_groups_issues_by_assignee(self):
        """Should group issues by assignee LDAP correctly."""
        # Create mock issues with different assignees
        issue1, issue2 = MagicMock(), MagicMock()
        issue1.fields.assignee.name = "alice"
        issue2.fields.assignee.name = "bob"
        issue3 = MagicMock()
        issue3.fields.assignee.name = "alice"  # Same as issue1

        result = group_incremental_issues_by_ldap([issue1, issue2, issue3])

        self.assertEqual(len(result), 2)  # Two unique users
        self.assertEqual(len(result["alice"]), 2)  # Alice: 2 issues
        self.assertEqual(len(result["bob"]), 1)  # Bob has 1 issue

    def test_skips_issues_without_assignee(self):
        """Should skip issues without assignee."""
        issue_no_assignee = MagicMock()
        issue_no_assignee.fields.assignee = None

        result = group_incremental_issues_by_ldap([issue_no_assignee])

        self.assertEqual(result, {})


class TestProcessIncrementalIssuesData(TestCase):
    """Test incremental issue data processing."""

    @patch("src.historical_data.jira_history_fetcher.JIRA_STATUS_ID_MAP")
    def test_processes_valid_issues(self, mock_status_map):
        """Should process valid issues and return proper data structure."""
        mock_issue = MagicMock()
        mock_issue.raw = {
            "id": "12345",
            "key": "PROJ-123",
            "fields": {
                "summary": "Test Issue",
                "project": {"id": "10001"},
                "status": {"id": "10002"},
            },
        }
        mock_status_map.get.return_value = JiraIssueStatus.TODO

        result = process_incremental_issues_data("test_user", [mock_issue])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["issue_id"], "12345")
        self.assertEqual(result[0]["redis_data"]["ldap"], "test_user")
        self.assertEqual(result[0]["redis_data"]["issue_key"], "PROJ-123")

    @patch("src.historical_data.jira_history_fetcher.JIRA_STATUS_ID_MAP")
    def test_skips_unknown_status(self, mock_status_map):
        """Should skip issues with unknown status."""
        mock_issue = MagicMock()
        mock_issue.raw = {"fields": {"status": {"id": "unknown"}}}
        mock_status_map.get.return_value = None

        result = process_incremental_issues_data("test_user", [mock_issue])

        self.assertEqual(len(result), 0)


class TestUpdateIncrementalIssueIndexes(TestCase):
    """Test incremental issue index updating functionality."""

    @patch(
        "src.historical_data.jira_history_fetcher.remove_updated_issue_previous_indexes"
    )
    def test_handles_new_and_existing_issues(self, mock_remove_indexes):
        """Should correctly handle new vs existing issues."""
        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline

        # Mock: first issue exists, second is new
        mock_redis_client.json().get.side_effect = [
            [{"ldap": "user1", "project_id": "123", "issue_status": "todo"}],  # exists
            None,  # new
        ]

        # Use realistic data structure that matches actual usage
        issues = [
            {
                "issue_id": "existing_1",
                "redis_data": {
                    "issue_key": "PROJ-1",
                    "issue_title": "Test Issue 1",
                    "project_id": "123",
                    "story_point": 5,
                    "issue_status": "done",  # Different from existing status
                    "ldap": "user1",
                    "finish_date": 20240719,
                },
            },
            {
                "issue_id": "new_1",
                "redis_data": {
                    "issue_key": "PROJ-2",
                    "issue_title": "Test Issue 2",
                    "project_id": "456",
                    "story_point": 3,
                    "issue_status": "todo",
                    "ldap": "user2",
                    "finish_date": None,
                },
            },
        ]
        created, updated = update_incremental_issue_indexes(issues, mock_redis_client)

        self.assertEqual(created, 1)
        self.assertEqual(updated, 1)
        # Should call remove_indexes for existing issue only (because status changed)
        mock_remove_indexes.assert_called_once()

    def test_raises_error_for_none_client(self):
        """Should raise ValueError when redis_client is None."""
        with self.assertRaises(ValueError):
            update_incremental_issue_indexes([], None)


class TestRemoveUpdatedIssuePreviousIndexes(TestCase):
    """Test removal of previous indexes for updated issues."""

    def test_removes_from_correct_redis_structure(self):
        """Should use appropriate Redis commands based on issue status."""
        mock_pipe = MagicMock()

        # Test with non-done status
        data = {"ldap": "user", "project_id": "1", "issue_status": "todo"}
        remove_updated_issue_previous_indexes("123", data, mock_pipe)
        mock_pipe.srem.assert_called()

        # Test with done status
        done_data = {"ldap": "user", "project_id": "1", "issue_status": "done"}
        remove_updated_issue_previous_indexes("456", done_data, mock_pipe)
        mock_pipe.zrem.assert_called()

    def test_raises_error_for_none_pipe(self):
        """Should raise ValueError when pipe is None."""
        with self.assertRaises(ValueError):
            remove_updated_issue_previous_indexes("123", {}, None)


class TestProcessUpdateJiraIssues(TestCase):
    """Test complete incremental update process."""

    @patch("src.historical_data.jira_history_fetcher.store_issues_in_redis")
    @patch("src.historical_data.jira_history_fetcher.update_incremental_issue_indexes")
    @patch("src.historical_data.jira_history_fetcher.fetch_incremental_issues")
    @patch("src.historical_data.jira_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.jira_history_fetcher.JiraClientFactory")
    def test_coordinates_incremental_update_workflow(
        self,
        mock_jira_factory,
        mock_redis_factory,
        mock_fetch,
        mock_update_indexes,
        mock_store,
    ):
        """Should coordinate the complete incremental update process."""
        # Setup clients
        mock_jira_factory.return_value.create_jira_client.return_value = MagicMock()
        mock_redis_factory.return_value.create_redis_client.return_value = MagicMock()

        # Setup workflow responses
        mock_issue = MagicMock()
        mock_issue.fields.assignee.name = "test_user"
        mock_fetch.return_value = [mock_issue]
        mock_update_indexes.return_value = (1, 0)  # 1 created, 0 updated
        mock_store.return_value = 1

        with patch(
            "src.historical_data.jira_history_fetcher.process_incremental_issues_data"
        ) as mock_process:
            mock_process.return_value = [{"issue_id": "123"}]

            result = process_update_jira_issues(24)

        # Verify workflow coordination
        self.assertEqual(result, 1)
        mock_fetch.assert_called_once()
        mock_process.assert_called_once_with("test_user", [mock_issue])
        mock_update_indexes.assert_called_once()
        mock_store.assert_called_once()

    @patch("src.historical_data.jira_history_fetcher.fetch_incremental_issues")
    @patch("src.historical_data.jira_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.jira_history_fetcher.JiraClientFactory")
    def test_returns_zero_for_empty_issues(
        self, mock_jira_factory, mock_redis_factory, mock_fetch
    ):
        """Should return 0 when no issues are found."""
        # Setup clients
        mock_jira_factory.return_value.create_jira_client.return_value = MagicMock()
        mock_redis_factory.return_value.create_redis_client.return_value = MagicMock()
        mock_fetch.return_value = []

        result = process_update_jira_issues(24)

        self.assertEqual(result, 0)
        mock_fetch.assert_called_once()


class TestFetchIssuesWithMetadata(TestCase):
    """Test Jira issue fetching and data processing."""

    def setUp(self):
        """Set up common test data."""
        self.sample_issue_data = {
            "id": "12345",
            "key": "PROJ-123",
            "fields": {
                "summary": "Sample Issue",
                "project": {"id": "10001"},
                "customfield_10106": 5,
                "status": {"id": "10002"},
                "resolutiondate": "2023-12-25T10:30:00.000+0000",
            },
        }

    @patch("src.historical_data.jira_history_fetcher.JIRA_STATUS_ID_MAP")
    def test_processes_valid_issues_correctly(self, mock_status_map):
        """Should extract and format issue data correctly."""
        mock_issue = MagicMock()
        mock_issue.raw = self.sample_issue_data
        mock_jira_client = MagicMock()
        mock_jira_client.search_issues.return_value = [mock_issue]
        mock_status_map.get.return_value = JiraIssueStatus.TODO

        result = fetch_issues_with_metadata("test_user", mock_jira_client)

        self.assertEqual(result["fetched_issues_count"], 1)
        self.assertEqual(result["excluded_issues_count"], 0)
        self.assertEqual(result["failed_to_parse_issues_count"], 0)
        self.assertEqual(len(result["valid_issues"]), 1)

        issue = result["valid_issues"][0]
        self.assertEqual(issue["issue_id"], "12345")

        redis_data = issue["redis_data"]
        self.assertEqual(redis_data["issue_key"], "PROJ-123")
        self.assertEqual(redis_data["issue_title"], "Sample Issue")
        self.assertEqual(redis_data["project_id"], "10001")
        self.assertEqual(redis_data["story_point"], 5)
        self.assertEqual(redis_data["issue_status"], JiraIssueStatus.TODO)
        self.assertEqual(redis_data["ldap"], "test_user")
        self.assertEqual(redis_data["finish_date"], 20231225)

    @patch(
        "src.historical_data.jira_history_fetcher.JIRA_EXCLUDED_STATUS_ID",
        "excluded_status",
    )
    def test_excludes_issues_with_excluded_status(self):
        """Should properly exclude issues with excluded status."""
        mock_issue = MagicMock()
        mock_issue.raw = {
            "id": "123",
            "key": "PROJ-123",
            "fields": {"status": {"id": "excluded_status"}},
        }
        mock_jira_client = MagicMock()
        mock_jira_client.search_issues.return_value = [mock_issue]

        result = fetch_issues_with_metadata("test_user", mock_jira_client)

        self.assertEqual(result["excluded_issues_count"], 1)
        self.assertEqual(len(result["valid_issues"]), 0)

    @patch("src.historical_data.jira_history_fetcher.JIRA_STATUS_ID_MAP")
    def test_handles_unknown_status_ids(self, mock_status_map):
        """Should count issues with unknown status as failed to parse."""
        mock_issue = MagicMock()
        mock_issue.raw = {
            "id": "123",
            "key": "PROJ-123",
            "fields": {"status": {"id": "unknown_status"}},
        }
        mock_jira_client = MagicMock()
        mock_jira_client.search_issues.return_value = [mock_issue]
        mock_status_map.get.return_value = None

        result = fetch_issues_with_metadata("test_user", mock_jira_client)

        self.assertEqual(result["failed_to_parse_issues_count"], 1)
        self.assertEqual(len(result["valid_issues"]), 0)


class TestStoreIssuesInRedis(TestCase):
    """Test Redis storage functionality."""

    def setUp(self):
        self.sample_issues = [
            {
                "issue_id": "12345",
                "redis_data": {
                    "issue_key": "PROJ-123",
                    "issue_title": "Test Issue",
                    "project_id": "10001",
                    "story_point": 5,
                    "issue_status": JiraIssueStatus.TODO,
                    "ldap": "test_user",
                    "finish_date": None,
                },
            }
        ]

    def test_stores_issues_successfully(self):
        """Should store issues and return success count."""
        mock_pipeline = MagicMock()
        mock_redis_client = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline

        result = store_issues_in_redis(self.sample_issues, mock_redis_client)

        self.assertEqual(result, 1)
        mock_redis_client.pipeline.assert_called_once()
        mock_pipeline.json().set.assert_called_once()
        mock_pipeline.execute.assert_called_once()

    def test_handles_empty_input_gracefully(self):
        """Should skip Redis when no issues provided."""
        mock_redis_client = MagicMock()

        result = store_issues_in_redis([], mock_redis_client)

        self.assertEqual(result, 0)
        mock_redis_client.pipeline.assert_not_called()


class TestFetchAndStoreIssuesForLdap(TestCase):
    """Test user-level issue processing workflow."""

    @patch("src.historical_data.jira_history_fetcher.fetch_issues_with_metadata")
    @patch("src.historical_data.jira_history_fetcher.store_issues_in_redis")
    def test_processes_user_successfully(self, mock_store, mock_fetch):
        """Should coordinate fetching and storing for a user."""
        mock_fetch.return_value = {
            "valid_issues": [{"issue_id": "123", "redis_data": {}}],
            "fetched_issues_count": 1,
            "excluded_issues_count": 0,
            "failed_to_parse_issues_count": 0,
        }
        mock_store.return_value = 1
        mock_jira_client = MagicMock()
        mock_redis_client = MagicMock()

        result = fetch_and_store_issues_for_ldap(
            "test_user", mock_jira_client, mock_redis_client
        )

        self.assertEqual(result["ldap"], "test_user")
        self.assertEqual(result["fetched_issues_count"], 1)
        self.assertEqual(result["stored_issues_count"], 1)
        self.assertEqual(result["failed_to_store_issues_count"], 0)

        mock_fetch.assert_called_once_with("test_user", mock_jira_client)
        mock_store.assert_called_once_with(
            [{"issue_id": "123", "redis_data": {}}], mock_redis_client
        )

    @patch("src.historical_data.jira_history_fetcher.fetch_issues_with_metadata")
    def test_handles_no_issues_found(self, mock_fetch):
        """Should handle users with no issues gracefully."""
        mock_fetch.return_value = {
            "valid_issues": [],
            "fetched_issues_count": 0,
            "excluded_issues_count": 0,
            "failed_to_parse_issues_count": 0,
        }
        mock_jira_client = MagicMock()
        mock_redis_client = MagicMock()

        result = fetch_and_store_issues_for_ldap(
            "empty_user", mock_jira_client, mock_redis_client
        )

        self.assertEqual(result["ldap"], "empty_user")
        self.assertEqual(result["fetched_issues_count"], 0)
        self.assertEqual(result["stored_issues_count"], 0)
        mock_fetch.assert_called_once_with("empty_user", mock_jira_client)
        mock_redis_client.pipeline.assert_not_called()


class TestProcessBackfillJiraIssues(TestCase):
    """Test complete backfill process."""

    @patch("src.historical_data.jira_history_fetcher.get_all_ldaps_and_displaynames")
    @patch("src.historical_data.jira_history_fetcher.fetch_and_store_issues_for_ldap")
    @patch("src.historical_data.jira_history_fetcher.JiraClientFactory")
    @patch("src.historical_data.jira_history_fetcher.RedisClientFactory")
    def test_processes_all_users_and_aggregates_results(
        self, mock_redis_factory, mock_jira_factory, mock_process_user, mock_get_ldaps
    ):
        """Should process all users and return aggregated statistics."""
        mock_get_ldaps.return_value = {"user1": "User One", "user2": "User Two"}
        mock_process_user.side_effect = [
            {
                "stored_issues_count": 10,
                "fetched_issues_count": 12,
                "excluded_issues_count": 1,
                "failed_to_parse_issues_count": 1,
                "failed_to_store_issues_count": 0,
            },
            {
                "stored_issues_count": 5,
                "fetched_issues_count": 6,
                "excluded_issues_count": 0,
                "failed_to_parse_issues_count": 1,
                "failed_to_store_issues_count": 0,
            },
        ]

        result = process_backfill_jira_issues()
        self.assertEqual(result, 15)
        self.assertEqual(mock_process_user.call_count, 2)

        mock_get_ldaps.assert_called_once()
        mock_jira_factory.assert_called_once()
        mock_redis_factory.assert_called_once()
        mock_process_user.assert_has_calls(
            [
                call("user1", ANY, ANY),
                call("user2", ANY, ANY),
            ],
            any_order=True,
        )

    @patch("src.historical_data.jira_history_fetcher.get_all_ldaps_and_displaynames")
    def test_raises_error_when_no_users_found(self, mock_get_ldaps):
        """Should raise RuntimeError when no users are found."""
        mock_get_ldaps.return_value = {}

        with self.assertRaises(RuntimeError) as context:
            process_backfill_jira_issues()

        self.assertIn("No ldaps found", str(context.exception))


class TestFetchJiraProjects(TestCase):
    """Test Jira projects fetching functionality."""

    def test_fetch_jira_projects_success(self):
        """Should fetch projects and return ID to name mapping."""
        mock_project1 = MagicMock()
        mock_project1.id = "10001"
        mock_project1.name = "Project Alpha"

        mock_project2 = MagicMock()
        mock_project2.id = "10002"
        mock_project2.name = "Project Beta"

        mock_jira_client = MagicMock()
        mock_jira_client.projects.return_value = [mock_project1, mock_project2]

        result = fetch_jira_projects(mock_jira_client)

        expected = {"10001": "Project Alpha", "10002": "Project Beta"}
        self.assertEqual(result, expected)
        mock_jira_client.projects.assert_called_once()

    def test_fetch_jira_projects_none_client(self):
        """Should raise ValueError when jira_client is None."""
        with self.assertRaises(ValueError) as context:
            fetch_jira_projects(None)

        self.assertIn("jira_client must not be None", str(context.exception))


class TestStoreJiraProjectsInRedis(TestCase):
    """Test Redis storage functionality."""

    @patch(
        "src.historical_data.jira_history_fetcher.JIRA_PROJECTS_KEY", "mock:project:key"
    )
    def test_store_jira_projects_success(self):
        """Should store projects in Redis with complete overwrite."""
        project_dict = {"10001": "Project Alpha", "10002": "Project Beta"}
        mock_redis_client = MagicMock()

        result = store_jira_projects_in_redis(project_dict, mock_redis_client)

        self.assertEqual(result, 2)
        mock_redis_client.delete.assert_called_once_with("mock:project:key")
        mock_redis_client.hset.assert_called_once_with(
            "mock:project:key", mapping=project_dict
        )

    @patch(
        "src.historical_data.jira_history_fetcher.JIRA_PROJECTS_KEY", "mock:project:key"
    )
    def test_store_empty_dict(self):
        """Should handle empty project dict gracefully."""
        mock_redis_client = MagicMock()

        result = store_jira_projects_in_redis({}, mock_redis_client)

        self.assertEqual(result, 0)
        mock_redis_client.delete.assert_not_called()
        mock_redis_client.hset.assert_not_called()

    def test_store_none_client(self):
        """Should raise ValueError when redis_client is None."""
        with self.assertRaises(ValueError):
            store_jira_projects_in_redis({"10001": "Test"}, None)


class TestProcessSyncJiraProjects(TestCase):
    """Test complete synchronization process."""

    @patch(
        "src.historical_data.jira_history_fetcher.JIRA_PROJECTS_KEY", "mock:project:key"
    )
    @patch("src.historical_data.jira_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.jira_history_fetcher.JiraClientFactory")
    def test_process_sync_success(self, mock_jira_factory, mock_redis_factory):
        """Should successfully sync projects from Jira to Redis."""
        mock_jira_client = MagicMock()
        mock_redis_client = MagicMock()

        mock_jira_factory.return_value.create_jira_client.return_value = (
            mock_jira_client
        )
        mock_redis_factory.return_value.create_redis_client.return_value = (
            mock_redis_client
        )

        mock_project = MagicMock()
        mock_project.id = "10001"
        mock_project.name = "Test Project"
        mock_jira_client.projects.return_value = [mock_project]

        result = process_sync_jira_projects()

        self.assertEqual(result, 1)
        mock_jira_client.projects.assert_called_once()
        mock_redis_client.delete.assert_called_once_with("mock:project:key")
        mock_redis_client.hset.assert_called_once_with(
            "mock:project:key", mapping={"10001": "Test Project"}
        )

    @patch(
        "src.historical_data.jira_history_fetcher.JIRA_PROJECTS_KEY", "mock:project:key"
    )
    @patch("src.historical_data.jira_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.jira_history_fetcher.JiraClientFactory")
    def test_process_sync_no_projects_error(
        self, mock_jira_factory, mock_redis_factory
    ):
        """Should raise RuntimeError when no projects found."""
        mock_jira_client = MagicMock()
        mock_redis_client = MagicMock()

        mock_jira_factory.return_value.create_jira_client.return_value = (
            mock_jira_client
        )
        mock_redis_factory.return_value.create_redis_client.return_value = (
            mock_redis_client
        )

        mock_jira_client.projects.return_value = []

        with self.assertRaises(RuntimeError) as context:
            process_sync_jira_projects()

        self.assertIn("No projects found in Jira", str(context.exception))
        mock_redis_client.delete.assert_not_called()
        mock_redis_client.hset.assert_not_called()


if __name__ == "__main__":
    main()
