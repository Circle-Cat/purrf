from unittest import TestCase, main
from unittest.mock import Mock
from backend.common.constants import JIRA_PROJECTS_KEY
from backend.frontend_service.jira_analytics_service import JiraAnalyticsService


class TestJiraAnalyticsService(TestCase):
    def setUp(self):
        self.mock_logger = Mock()
        self.mock_redis = Mock()
        self.mock_retry_utils = Mock()
        self.jira_service = JiraAnalyticsService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            retry_utils=self.mock_retry_utils,
        )

    def test_get_all_jira_projects_success(self):
        mock_project_data = {"10503": "Intern Practice", "24998": "Purrf"}
        self.mock_retry_utils.get_retry_on_transient.return_value = mock_project_data

        result = self.jira_service.get_all_jira_projects()

        self.assertEqual(result, mock_project_data)
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            self.mock_redis.hgetall, JIRA_PROJECTS_KEY
        )

    def test_get_all_jira_projects_empty(self):
        self.mock_retry_utils.get_retry_on_transient.return_value = {}

        result = self.jira_service.get_all_jira_projects()

        self.assertEqual(result, {})
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


if __name__ == "__main__":
    main()
