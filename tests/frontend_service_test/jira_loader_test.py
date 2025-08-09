from unittest import TestCase, main
from unittest.mock import patch, Mock
from src.frontend_service.jira_loader import (
    get_issue_ids_in_timerange,
    _get_issues_for_status,
    _validate_issue_ids,
    _build_final_result,
    process_get_issue_detail_batch,
)
from src.common.constants import JiraIssueStatus


class TestJiraLoader(TestCase):
    @patch("src.frontend_service.jira_loader.RedisClientFactory.create_redis_client")
    def test_get_issue_ids_in_timerange_todo(self, mock_create_redis_client):
        mock_redis = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = [["101", "102"]]
        mock_redis.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis

        result = get_issue_ids_in_timerange(
            status="todo", ldaps=["alice"], project_ids=["projectA"]
        )
        self.assertEqual(result, {"todo": {"alice": {"projectA": [101, 102]}}})

    @patch("src.frontend_service.jira_loader.RedisClientFactory.create_redis_client")
    def test_get_issue_ids_in_timerange_done_with_dates(self, mock_create_redis_client):
        mock_redis = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = [["201", "202"]]
        mock_redis.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis

        result = get_issue_ids_in_timerange(
            status="done",
            ldaps=["bob"],
            project_ids=["projectB"],
            start_date="2024-01-01",
            end_date="2024-01-31",
        )
        self.assertEqual(result, {"done": {"bob": {"projectB": [201, 202]}}})

    @patch("src.frontend_service.jira_loader._get_issues_for_status")
    @patch("src.frontend_service.jira_loader.RedisClientFactory.create_redis_client")
    def test_get_issue_ids_in_timerange_all(
        self, mock_create_redis_client, mock_get_issues
    ):
        mock_create_redis_client.return_value = Mock()

        mock_get_issues.side_effect = [
            {"alice": {"projectA": [301]}},
            {"alice": {"projectA": [302]}},
            {"alice": {"projectA": [303]}},
        ]

        result = get_issue_ids_in_timerange(
            status="all",
            ldaps=["alice"],
            project_ids=["projectA"],
            start_date="2024-01-01",
            end_date="2024-01-31",
        )

        self.assertEqual(result["todo"]["alice"]["projectA"], [301])
        self.assertEqual(result["in_progress"]["alice"]["projectA"], [302])
        self.assertEqual(result["done"]["alice"]["projectA"], [303])

    def test_get_issue_ids_in_timerange_missing_ldaps(self):
        with self.assertRaises(ValueError) as context:
            get_issue_ids_in_timerange(
                status="todo", ldaps=None, project_ids=["projectA"]
            )
        self.assertIn("ldaps is required", str(context.exception))

    def test_get_issue_ids_in_timerange_missing_project_ids(self):
        with self.assertRaises(ValueError) as context:
            get_issue_ids_in_timerange(status="todo", ldaps=["alice"], project_ids=None)
        self.assertIn("project_ids is required", str(context.exception))

    def test_get_issue_ids_in_timerange_invalid_status(self):
        with self.assertRaises(ValueError) as context:
            get_issue_ids_in_timerange(
                status="not_a_status", ldaps=["alice"], project_ids=["projectA"]
            )
        self.assertIn("Invalid status", str(context.exception))

    def test_get_issues_for_status_pipeline(self):
        mock_redis = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = [["101"], ["102"], ["201", "202"], []]
        mock_redis.pipeline.return_value = mock_pipeline

        result = _get_issues_for_status(
            mock_redis, JiraIssueStatus.TODO, ["alice", "bob"], ["projectA", "projectB"]
        )
        self.assertEqual(result["alice"]["projectA"], [101])
        self.assertEqual(result["alice"]["projectB"], [102])
        self.assertEqual(result["bob"]["projectA"], [201, 202])
        self.assertEqual(result["bob"]["projectB"], [])

    def test_get_issues_for_status_pipeline_exception(self):
        mock_redis = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = Exception("Pipeline error")
        mock_redis.pipeline.return_value = mock_pipeline

        with self.assertRaises(Exception) as context:
            _get_issues_for_status(
                mock_redis, JiraIssueStatus.TODO, ["alice"], ["projectA"]
            )
        self.assertIn("Pipeline error", str(context.exception))


class TestValidateIssueIds(TestCase):
    """Test _validate_issue_ids function."""

    def test_valid_conversion(self):
        """Test valid input conversion."""
        result = _validate_issue_ids(["123", 456])
        self.assertEqual(result, [123, 456])

    def test_invalid_input(self):
        """Test invalid inputs raise ValueError."""
        test_cases = [None, [], "not_list", ["abc", 123]]
        for invalid_input in test_cases:
            with self.assertRaises(ValueError):
                _validate_issue_ids(invalid_input)


class TestBuildFinalResult(TestCase):
    """Test _build_final_result function."""

    def test_normal_case(self):
        """Test normal case with complete data."""
        validated_issue_ids = [101, 102]
        issue_details = {
            101: {
                "ldap": "user1",
                "finish_date": 20230712,
                "issue_key": "ISSUE-101",
                "story_point": 3,
                "project_id": 111,
                "issue_status": "done",
                "issue_title": "Fix bug",
            },
            102: None,  # Issue not found
        }
        project_names = {"111": "Test Project"}

        result = _build_final_result(validated_issue_ids, issue_details, project_names)

        # Check successful case
        self.assertEqual(result["101"]["project_name"], "Test Project")
        self.assertEqual(result["101"]["ldap"], "user1")
        # Check missing case
        self.assertIsNone(result["102"])


class TestProcessGetIssueDetailBatch(TestCase):
    """Integration tests for process_get_issue_detail_batch."""

    @patch("src.frontend_service.jira_loader.RedisClientFactory.create_redis_client")
    def test_success_case(self, mock_create_redis_client):
        """Test successful execution."""
        mock_redis = Mock()
        mock_pipeline = Mock()
        mock_pipeline.json.return_value = mock_pipeline

        mock_pipeline.execute.return_value = [
            [
                {
                    "ldap": "user1",
                    "finish_date": 20230712,
                    "issue_key": "ISSUE-101",
                    "story_point": 3,
                    "project_id": 111,
                    "issue_status": "done",
                    "issue_title": "Fix bug",
                }
            ],
            None,  # Second issue not found
        ]
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis.hmget.return_value = ["Test Project"]
        mock_create_redis_client.return_value = mock_redis

        result = process_get_issue_detail_batch(["101", "102"])

        # Check successful issue
        self.assertEqual(result["101"]["project_name"], "Test Project")
        self.assertEqual(result["101"]["ldap"], "user1")
        # Check missing issue
        self.assertIsNone(result["102"])

    def test_validation_errors(self):
        """Test input validation."""
        with self.assertRaises(ValueError):
            process_get_issue_detail_batch(None)

        with self.assertRaises(ValueError):
            process_get_issue_detail_batch(["abc"])

    @patch("src.frontend_service.jira_loader.RedisClientFactory.create_redis_client")
    def test_redis_exception(self, mock_create_redis_client):
        """Test Redis exception handling."""
        mock_redis = Mock()
        mock_pipeline = Mock()
        mock_pipeline.json.return_value = mock_pipeline
        mock_pipeline.execute.side_effect = Exception("Redis error")
        mock_redis.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis

        with self.assertRaises(Exception):
            process_get_issue_detail_batch(["101"])


if __name__ == "__main__":
    main()
