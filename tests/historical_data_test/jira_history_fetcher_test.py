from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from src.historical_data.jira_history_fetcher import (
    fetch_jira_projects,
    store_jira_projects_in_redis,
    process_sync_jira_projects,
)


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
