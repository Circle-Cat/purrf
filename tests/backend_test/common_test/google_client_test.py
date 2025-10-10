from unittest import TestCase, main
from unittest.mock import patch, Mock
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google.cloud.pubsub_v1 import SubscriberClient, PublisherClient
from backend.common.google_client import GoogleClient
from backend.common.constants import GOOGLE_USER_SCOPES_LIST, GOOGLE_ADMIN_SCOPES_LIST
import os

TEST_PROJECT_NAME = "test-project"
TEST_USER_EMAIL = "test@example.com"
TEST_SERVICE_ACCOUNT_EMAIL = "test-service-account@project.iam.gserviceaccount.com"
TEST_ADMIN_EMAIL = "admin@example.com"

API_CLIENT_CONFIGS = [
    ("create_chat_client", "chat", "v1", GOOGLE_USER_SCOPES_LIST),
    ("create_people_client", "people", "v1", GOOGLE_USER_SCOPES_LIST),
    ("create_workspaceevents_client", "workspaceevents", "v1", GOOGLE_USER_SCOPES_LIST),
    ("create_calendar_client", "calendar", "v3", GOOGLE_USER_SCOPES_LIST),
    ("create_reports_client", "admin", "reports_v1", GOOGLE_ADMIN_SCOPES_LIST),
]


class MockRetryUtils:
    """Mock for the injected retry_utils to simulate its behavior."""

    def __init__(self, *args, **kwargs):
        pass

    def get_retry_on_transient(self, func):
        """
        Immediately call the function without any retry mechanism for simple tests.
        We'll use a SideEffect in specific retry tests.
        """
        return func()


class TestGoogleClient(TestCase):
    """Unit tests for the non-singleton GoogleClient class."""

    def setUp(self):
        """Set up common mocks and the client instance for each test."""
        env = {
            "USER_EMAIL": TEST_USER_EMAIL,
            "SERVICE_ACCOUNT_EMAIL": TEST_SERVICE_ACCOUNT_EMAIL,
            "ADMIN_EMAIL": TEST_ADMIN_EMAIL,
        }
        self.env_patcher = patch.dict(os.environ, env)
        self.env_patcher.start()

        self.mock_logger = Mock()
        self.mock_retry_utils_instance = Mock(spec=MockRetryUtils)

        def mock_retry_caller(func):
            return func()

        self.mock_retry_utils_instance.get_retry_on_transient.side_effect = (
            mock_retry_caller
        )

        self.client = GoogleClient(
            logger=self.mock_logger,
            retry_utils=self.mock_retry_utils_instance,
        )

        self.mock_credentials = Mock(spec=ServiceAccountCredentials)
        self.mock_impersonated_credentials = Mock(spec=UserCredentials)
        self.mock_service = Mock()

    def tearDown(self):
        self.env_patcher.stop()

    def test_init_success(self):
        """Test successful initialization and attribute assignment."""
        self.assertEqual(self.client._user_email, TEST_USER_EMAIL)
        self.assertEqual(self.client._service_account_email, TEST_SERVICE_ACCOUNT_EMAIL)
        self.assertEqual(self.client._admin_email, TEST_ADMIN_EMAIL)
        self.assertIs(self.client.logger, self.mock_logger)
        self.assertIsInstance(self.client._credentials, dict)

    def test_init_missing_args(self):
        """Test ValueErrors for missing required init arguments."""
        required_args = {
            "logger": self.mock_logger,
            "retry_utils": self.mock_retry_utils_instance,
        }

        for key in required_args:
            with self.subTest(missing_arg=key):
                temp_args = required_args.copy()
                temp_args[key] = None

                with self.assertRaises(ValueError) as cm:
                    GoogleClient(**temp_args)

                self.assertIn(key, str(cm.exception))

    @patch("backend.common.google_client.default")
    @patch("backend.common.google_client.ImpersonatedCredentials")
    def test_get_impersonate_credentials_success_and_caching(
        self, mock_impersonated_creds, mock_default
    ):
        """Tests successful credentials retrieval, impersonation, and caching."""

        mock_default.return_value = (self.mock_credentials, TEST_PROJECT_NAME)
        mock_impersonated_creds.return_value = self.mock_impersonated_credentials

        creds1 = self.client._get_impersonate_credentials(user_email=TEST_USER_EMAIL)

        mock_default.assert_called_once()
        mock_impersonated_creds.assert_called_once_with(
            source_credentials=self.mock_credentials,
            target_principal=TEST_SERVICE_ACCOUNT_EMAIL,
            target_scopes=GOOGLE_USER_SCOPES_LIST,
            subject=TEST_USER_EMAIL,
        )
        self.assertIs(creds1, self.mock_impersonated_credentials)
        self.assertIn(TEST_USER_EMAIL, self.client._credentials)

        creds2 = self.client._get_impersonate_credentials(user_email=TEST_USER_EMAIL)

        mock_default.assert_called_once()
        mock_impersonated_creds.assert_called_once()
        self.assertIs(creds1, creds2)

    @patch("backend.common.google_client.default")
    def test_get_impersonate_credentials_adc_failure(self, mock_default):
        """Test failure when Application Default Credentials (ADC) cannot be obtained."""

        mock_default.return_value = (None, TEST_PROJECT_NAME)

        with self.assertRaises(ValueError) as cm:
            self.client._get_impersonate_credentials()

        self.assertIn("Google authentication service unavailable", str(cm.exception))

    @patch("backend.common.google_client.default")
    @patch("backend.common.google_client.ImpersonatedCredentials")
    def test_get_impersonate_credentials_impersonation_failure(
        self, mock_impersonated_creds, mock_default
    ):
        """Test failure during the ImpersonatedCredentials creation."""

        mock_default.return_value = (self.mock_credentials, TEST_PROJECT_NAME)
        mock_impersonated_creds.side_effect = Exception("Auth failed")

        with self.assertRaises(ValueError) as cm:
            self.client._get_impersonate_credentials()

        self.assertIn(
            "Authentication failed. Please contact support", str(cm.exception)
        )
        self.mock_logger.error.assert_called()

    @patch("backend.common.google_client.build")
    @patch.object(GoogleClient, "_get_impersonate_credentials")
    def test_create_client_flow(self, mock_get_creds, mock_build):
        """Tests the full client creation flow for a generic API."""

        mock_get_creds.return_value = self.mock_impersonated_credentials
        mock_build.return_value = self.mock_service

        api_name = "test_api"
        api_version = "v1"

        client_instance = self.client._create_client(api_name, api_version)

        self.mock_retry_utils_instance.get_retry_on_transient.assert_called_once()
        mock_build.assert_called_once_with(
            api_name, api_version, credentials=self.mock_impersonated_credentials
        )
        self.assertIs(client_instance, self.mock_service)

    def test_api_client_creation_methods(self):
        """Test all googleapiclient wrapper methods."""

        with patch.object(self.client, "_create_client") as mock_create_client:
            mock_create_client.return_value = self.mock_service

            for (
                function_name,
                api_name,
                api_version,
                expected_scopes,
            ) in API_CLIENT_CONFIGS:
                with self.subTest(function_name=function_name):
                    create_method = getattr(self.client, function_name)
                    client_instance = create_method()

                    self.assertIs(client_instance, self.mock_service)

                    if function_name == "create_reports_client":
                        mock_create_client.assert_called_with(
                            api_name, api_version, TEST_ADMIN_EMAIL, expected_scopes
                        )
                    else:
                        mock_create_client.assert_called_with(api_name, api_version)

            mock_create_client.call_count = 0

    @patch("backend.common.google_client.build")
    @patch.object(GoogleClient, "_get_impersonate_credentials")
    def test_create_client_retry_mechanism_success(self, mock_get_creds, mock_build):
        """
        Test that retry logic is used correctly by injecting a mock retry_utils.
        """

        mock_impersonated_credentials = Mock(spec=UserCredentials)
        mock_get_creds.return_value = mock_impersonated_credentials
        mock_build.return_value = self.mock_service

        self.client.create_chat_client()

        self.mock_retry_utils_instance.get_retry_on_transient.assert_called_once()

        mock_build.assert_called_once_with(
            "chat", "v1", credentials=mock_impersonated_credentials
        )

    @patch("backend.common.google_client.SubscriberClient")
    def test_create_subscriber_client(self, mock_subscriber_client):
        """Test creation of the Pub/Sub Subscriber client."""

        mock_subscriber_instance = Mock(spec=SubscriberClient)
        mock_subscriber_client.return_value = mock_subscriber_instance

        subscriber_client = self.client.create_subscriber_client()

        mock_subscriber_client.assert_called_once_with()  # Check no arguments are passed
        self.assertIs(subscriber_client, mock_subscriber_instance)

    @patch("backend.common.google_client.PublisherClient")
    def test_create_publisher_client(self, mock_publisher_client):
        """Test creation of the Pub/Sub Publisher client."""

        mock_publisher_instance = Mock(spec=PublisherClient)
        mock_publisher_client.return_value = mock_publisher_instance

        publisher_client = self.client.create_publisher_client()

        mock_publisher_client.assert_called_once_with()
        self.assertIs(publisher_client, mock_publisher_instance)


if __name__ == "__main__":
    main()
