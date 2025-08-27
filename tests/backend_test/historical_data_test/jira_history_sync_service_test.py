from unittest import TestCase, main
from unittest.mock import MagicMock, patch
from backend.historical_data.jira_history_sync_service import JiraHistorySyncService


class TestJiraHistorySyncService(TestCase):
    """Test JiraHistorySyncService functionality."""

    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_jira_client = MagicMock()
        self.mock_redis_client = MagicMock()
        self.service = JiraHistorySyncService(
            logger=self.mock_logger,
            jira_client=self.mock_jira_client,
            redis_client=self.mock_redis_client,
        )

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
            JiraHistorySyncService(None, self.mock_jira_client, self.mock_redis_client)

        with self.assertRaises(ValueError):
            JiraHistorySyncService(self.mock_logger, None, self.mock_redis_client)

        with self.assertRaises(ValueError):
            JiraHistorySyncService(self.mock_logger, self.mock_jira_client, None)


if __name__ == "__main__":
    main()
