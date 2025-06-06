import os
import unittest
from unittest.mock import patch, MagicMock

from src.common.environment_constants import (
    JIRA_SERVER,
    JIRA_USER,
    JIRA_PASSWORD,
)
from src.common.jira_client import JiraClientFactory

TEST_ENV = {
    JIRA_SERVER: "https://jira.example.com",
    JIRA_USER: "testuser",
    JIRA_PASSWORD: "testpass",
}


class TestJiraClientFactory(unittest.TestCase):
    def setUp(self):
        JiraClientFactory._instance = None

    def test_create_client_singleton(self):
        with (
            patch.dict(os.environ, TEST_ENV, clear=True),
            patch("src.common.jira_client.JIRA") as mock_jira,
            patch(
                "src.common.jira_client.JiraClientFactory._get_credentials"
            ) as mock_get_credentials,
        ):
            mock_jira.return_value = MagicMock()
            mock_get_credentials.return_value = {
                "server": "https://jira.example.com",
                "username": "testuser",
                "password": "testpass",
            }

            factory = JiraClientFactory()
            client1 = factory.create_jira_client()
            client2 = factory.create_jira_client()

            self.assertIs(client1, client2)
            mock_jira.assert_called_once()

            _, kwargs = mock_jira.call_args
            self.assertEqual(kwargs.get("server"), "https://jira.example.com")
            self.assertEqual(kwargs.get("basic_auth"), ("testuser", "testpass"))

            self.assertEqual(mock_get_credentials.call_count, 1)

    def test_missing_env_vars(self):
        env = {
            JIRA_SERVER: "https://jira.example.com",
            JIRA_PASSWORD: "testpass",  # missing JIRA_USER
        }
        with patch.dict(os.environ, env, clear=True):
            factory = JiraClientFactory()
            with self.assertRaises(ValueError) as cm:
                factory.create_jira_client()
            self.assertIn(JIRA_USER, str(cm.exception))

    def test_retry_on_failure(self):
        with (
            patch.dict(os.environ, TEST_ENV, clear=True),
            patch("src.common.jira_client.JIRA") as mock_jira,
        ):
            mock_jira.side_effect = [
                Exception("fail 1"),
                Exception("fail 2"),
                MagicMock(),
            ]
            factory = JiraClientFactory()
            client = factory.create_jira_client()

            self.assertEqual(mock_jira.call_count, 3)
            self.assertIsNotNone(client)

    def test_retry_exceeds_limit(self):
        with (
            patch.dict(os.environ, TEST_ENV, clear=True),
            patch("src.common.jira_client.JIRA") as mock_jira,
        ):
            mock_jira.side_effect = Exception("Permanent failure")
            factory = JiraClientFactory()
            with self.assertRaises(Exception):
                factory.create_jira_client()
            self.assertEqual(mock_jira.call_count, 3)


if __name__ == "__main__":
    unittest.main()
