from unittest import TestCase, main
from unittest.mock import patch, Mock

from src.frontend_service.jira_loader import (
    _validate_issue_ids,
    _build_final_result,
    process_get_issue_detail_batch,
)


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
