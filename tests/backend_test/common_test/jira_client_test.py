import unittest
from unittest.mock import patch, MagicMock
from backend.common.jira_client import JiraClient
from jira.exceptions import JIRAError
from backend.common.environment_constants import JIRA_PASSWORD


class TestJraClient(unittest.TestCase):
    """Unit tests for the JiraClient class."""

    def setUp(self):
        """Set up common mocks and variables for each test."""
        self.server = "https://test.jira.com"
        self.user = "test_user"
        self.password = "test_password"
        self.mock_logger = MagicMock()
        self.mock_retry_utils = MagicMock()

    def test_initialization_fails_with_missing_parameters(self):
        """Test that __init__ raises ValueError if required parameters are missing."""
        with self.assertRaisesRegex(
            ValueError, "Jira server and user must be provided."
        ):
            JiraClient(
                jira_server="",
                jira_user=self.user,
                logger=self.mock_logger,
                retry_utils=self.mock_retry_utils,
            )

        with self.assertRaisesRegex(
            ValueError, "Jira server and user must be provided."
        ):
            JiraClient(
                jira_server=self.server,
                jira_user="",
                logger=self.mock_logger,
                retry_utils=self.mock_retry_utils,
            )

    @patch("backend.common.jira_client.os.getenv")
    @patch("backend.common.jira_client.JIRA")
    def test_successful_initialization_with_retry_utils(
        self, mock_jira_class, mock_os_getenv
    ):
        """Test successful initialization uses retry utils and verifies the connection."""
        mock_os_getenv.return_value = self.password
        mock_jira_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_instance
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda func: func()

        JiraClient(
            jira_server=self.server,
            jira_user=self.user,
            logger=self.mock_logger,
            retry_utils=self.mock_retry_utils,
        )

        mock_os_getenv.assert_called_once_with(JIRA_PASSWORD)
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()
        mock_jira_class.assert_called_once_with(
            server=self.server, basic_auth=(self.user, self.password)
        )
        mock_jira_instance.server_info.assert_called_once()
        self.mock_logger.info.assert_any_call("Created Jira client successfully.")

    @patch("backend.common.jira_client.os.getenv")
    @patch("backend.common.jira_client.JIRA")
    def test_server_url_is_stripped(self, mock_jira_class, mock_os_getenv):
        """Test that trailing slashes are removed from the server URL."""
        mock_os_getenv.return_value = self.password
        mock_jira_class.return_value = MagicMock()
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda func: func()
        server_with_slashes = "https://test.jira.com///"

        JiraClient(
            jira_server=server_with_slashes,
            jira_user=self.user,
            logger=self.mock_logger,
            retry_utils=self.mock_retry_utils,
        )

        _, called_kwargs = mock_jira_class.call_args
        self.assertEqual(called_kwargs["server"], self.server)

    @patch("backend.common.jira_client.os.getenv")
    def test_connection_failure_after_retries(self, mock_os_getenv):
        """Test that an exception is raised if the connection fails after all retries."""
        mock_os_getenv.return_value = self.password
        error_message = "Authentication failed"
        self.mock_retry_utils.get_retry_on_transient.side_effect = JIRAError(
            text=error_message
        )

        with self.assertRaises(JIRAError) as context:
            JiraClient(
                jira_server=self.server,
                jira_user=self.user,
                logger=self.mock_logger,
                retry_utils=self.mock_retry_utils,
            )

        self.assertIn(error_message, str(context.exception))
        self.mock_logger.error.assert_called_once()
        self.assertIn(
            "Failed to create Jira client", self.mock_logger.error.call_args[0][0]
        )

    @patch("backend.common.jira_client.os.getenv")
    def test_raises_value_error_if_password_env_var_is_missing(self, mock_os_getenv):
        """Test that a ValueError is raised if the JIRA_PASSWORD environment variable is not set."""
        mock_os_getenv.return_value = None
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda func: func()

        with self.assertRaisesRegex(
            ValueError, "Jira password not found in environment variable"
        ):
            JiraClient(
                jira_server=self.server,
                jira_user=self.user,
                logger=self.mock_logger,
                retry_utils=self.mock_retry_utils,
            )


if __name__ == "__main__":
    unittest.main()
