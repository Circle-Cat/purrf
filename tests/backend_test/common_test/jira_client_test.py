import unittest
from unittest.mock import patch, MagicMock
from backend.common.jira_client import JiraClient
from jira.exceptions import JIRAError
from backend.common.environment_constants import JIRA_PASSWORD, TAILSCALE_PROXY


class TestJraClient(unittest.TestCase):
    """Unit tests for the JiraClient class."""

    def setUp(self):
        """Set up common mocks and variables for each test."""
        self.server = "https://test.jira.com"
        self.user = "test_user"
        self.password = "test_password"
        self.mock_logger = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda func: func()

    def _build_client(self, jira_server=None, jira_user=None):
        """Builds a JiraClient with the test defaults."""
        return JiraClient(
            jira_server=self.server if jira_server is None else jira_server,
            jira_user=self.user if jira_user is None else jira_user,
            logger=self.mock_logger,
            retry_utils=self.mock_retry_utils,
        )

    @patch("backend.common.jira_client.os.getenv")
    def test_initialization_fails_with_missing_parameters(self, mock_os_getenv):
        """Test that __init__ raises ValueError if required parameters are missing."""
        mock_os_getenv.return_value = self.password

        with self.assertRaisesRegex(
            ValueError, "Jira server and user must be provided."
        ):
            self._build_client(jira_server="")

        with self.assertRaisesRegex(
            ValueError, "Jira server and user must be provided."
        ):
            self._build_client(jira_user="")

    @patch("backend.common.jira_client.os.getenv")
    def test_raises_value_error_if_password_env_var_is_missing(self, mock_os_getenv):
        """Test that a missing JIRA_PASSWORD fails at construction, before any connection.

        Missing configuration is a broken deployment: it should stop the
        process rather than surface on a request hours later.
        """
        mock_os_getenv.return_value = None

        with self.assertRaisesRegex(
            ValueError, "Jira password not found in environment variable"
        ):
            self._build_client()

    @patch("backend.common.jira_client.os.getenv")
    @patch("backend.common.jira_client.JIRA")
    def test_construction_does_not_connect(self, mock_jira_class, mock_os_getenv):
        """Test that constructing the client reaches no further than the environment.

        Jira being unreachable, or rejecting the credential, must not stop a
        process whose other routes never touch Jira.
        """
        mock_os_getenv.side_effect = (
            lambda key: self.password if key == JIRA_PASSWORD else None
        )

        self._build_client()

        mock_jira_class.assert_not_called()
        self.mock_retry_utils.get_retry_on_transient.assert_not_called()

    @patch("backend.common.jira_client.os.getenv")
    @patch("backend.common.jira_client.JIRA")
    def test_first_use_connects_and_verifies(self, mock_jira_class, mock_os_getenv):
        """Test that the first get_jira_client() call connects and verifies the connection."""
        mock_os_getenv.side_effect = (
            lambda key: self.password if key == JIRA_PASSWORD else None
        )
        mock_jira_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_instance

        client = self._build_client().get_jira_client()

        self.assertIs(client, mock_jira_instance)
        mock_os_getenv.assert_any_call(JIRA_PASSWORD)
        mock_os_getenv.assert_any_call(TAILSCALE_PROXY)
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()
        mock_jira_class.assert_called_once_with(
            server=self.server,
            basic_auth=(self.user, self.password),
            proxies={"http": "", "https": ""},
        )
        mock_jira_instance.server_info.assert_called_once()

    @patch("backend.common.jira_client.os.getenv")
    @patch("backend.common.jira_client.JIRA")
    def test_connection_is_reused_across_calls(self, mock_jira_class, mock_os_getenv):
        """Test that a connection is opened once and reused by later calls."""
        mock_os_getenv.side_effect = (
            lambda key: self.password if key == JIRA_PASSWORD else None
        )
        mock_jira_class.return_value = MagicMock()
        jira_client = self._build_client()

        first = jira_client.get_jira_client()
        second = jira_client.get_jira_client()

        self.assertIs(first, second)
        mock_jira_class.assert_called_once()

    @patch("backend.common.jira_client.os.getenv")
    @patch("backend.common.jira_client.JIRA")
    def test_proxy_is_used_when_configured(self, mock_jira_class, mock_os_getenv):
        """Test that TAILSCALE_PROXY, when set, is passed to the Jira connection."""
        proxy = "http://outbound.tailscale.svc.cluster.local:1055"
        mock_os_getenv.side_effect = lambda key: {
            JIRA_PASSWORD: self.password,
            TAILSCALE_PROXY: proxy,
        }.get(key)
        mock_jira_class.return_value = MagicMock()

        self._build_client().get_jira_client()

        _, called_kwargs = mock_jira_class.call_args
        self.assertEqual(called_kwargs["proxies"], {"http": proxy, "https": proxy})

    @patch("backend.common.jira_client.os.getenv")
    @patch("backend.common.jira_client.JIRA")
    def test_server_url_is_stripped(self, mock_jira_class, mock_os_getenv):
        """Test that trailing slashes are removed from the server URL."""
        mock_os_getenv.return_value = self.password
        mock_jira_class.return_value = MagicMock()

        self._build_client(jira_server="https://test.jira.com///").get_jira_client()

        _, called_kwargs = mock_jira_class.call_args
        self.assertEqual(called_kwargs["server"], self.server)

    @patch("backend.common.jira_client.os.getenv")
    def test_connection_failure_after_retries(self, mock_os_getenv):
        """Test that a failure to connect is raised to the caller that asked for the client."""
        mock_os_getenv.return_value = self.password
        error_message = "Authentication failed"
        self.mock_retry_utils.get_retry_on_transient.side_effect = JIRAError(
            text=error_message
        )
        jira_client = self._build_client()

        with self.assertRaises(JIRAError) as context:
            jira_client.get_jira_client()

        self.assertIn(error_message, str(context.exception))
        self.mock_logger.error.assert_called_once()

    @patch("backend.common.jira_client.os.getenv")
    @patch("backend.common.jira_client.JIRA")
    def test_failed_connection_is_retried_on_the_next_call(
        self, mock_jira_class, mock_os_getenv
    ):
        """Test that a failed attempt is not cached, so recovery needs no restart.

        Caching the failure would leave the process serving errors long after
        Jira came back.
        """
        mock_os_getenv.return_value = self.password
        mock_jira_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_instance
        self.mock_retry_utils.get_retry_on_transient.side_effect = [
            JIRAError(text="Jira is down"),
            mock_jira_instance,
        ]
        jira_client = self._build_client()

        with self.assertRaises(JIRAError):
            jira_client.get_jira_client()

        self.assertIs(jira_client.get_jira_client(), mock_jira_instance)


if __name__ == "__main__":
    unittest.main()
