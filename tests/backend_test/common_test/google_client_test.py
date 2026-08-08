from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase, main
from unittest.mock import patch, Mock
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google.cloud.pubsub_v1 import SubscriberClient, PublisherClient
from backend.common.google_client import GoogleClient
from backend.common.constants import GOOGLE_USER_SCOPES_LIST, GOOGLE_ADMIN_SCOPES_LIST
import os
import threading
import time

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


class ConcurrencyProbeService:
    """A fake API resource that reports being used by two threads at once.

    It stands in for one ``googleapiclient`` service, which owns a single
    ``httplib2`` connection. Every call is held open briefly so that threads
    sharing one instance overlap inside it.
    """

    def __init__(self, conflicts, hold_seconds=0.05):
        self._conflicts = conflicts
        self._hold_seconds = hold_seconds
        self._in_flight = 0
        self._lock = threading.Lock()

    def events(self):
        return self

    def list(self, **_kwargs):
        return self

    def execute(self):
        with self._lock:
            self._in_flight += 1
            overlapping = self._in_flight
        if overlapping > 1:
            self._conflicts.append(overlapping)
        time.sleep(self._hold_seconds)
        with self._lock:
            self._in_flight -= 1
        return {"items": []}


THREAD_COUNT = 10


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
        self.assertEqual(len(self.client._credentials), 1)

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

    @patch("backend.common.google_client.default")
    @patch("backend.common.google_client.ImpersonatedCredentials")
    def test_same_email_with_different_scopes_gets_its_own_credentials(
        self, mock_impersonated_creds, mock_default
    ):
        """Scopes decide what a credential may do, so they belong in the key."""

        mock_default.return_value = (self.mock_credentials, TEST_PROJECT_NAME)
        mock_impersonated_creds.side_effect = lambda **_kwargs: Mock(
            spec=UserCredentials
        )

        user_creds = self.client._get_impersonate_credentials(
            user_email=TEST_USER_EMAIL, scopes=GOOGLE_USER_SCOPES_LIST
        )
        admin_creds = self.client._get_impersonate_credentials(
            user_email=TEST_USER_EMAIL, scopes=GOOGLE_ADMIN_SCOPES_LIST
        )

        self.assertIsNot(user_creds, admin_creds)
        self.assertEqual(
            [
                call.kwargs["target_scopes"]
                for call in mock_impersonated_creds.call_args_list
            ],
            [GOOGLE_USER_SCOPES_LIST, GOOGLE_ADMIN_SCOPES_LIST],
        )

    @patch("backend.common.google_client.default")
    @patch("backend.common.google_client.ImpersonatedCredentials")
    def test_same_scopes_in_a_different_order_reuse_one_credential(
        self, mock_impersonated_creds, mock_default
    ):
        """Order carries no authority, so a reordered list is the same request."""

        mock_default.return_value = (self.mock_credentials, TEST_PROJECT_NAME)
        mock_impersonated_creds.side_effect = lambda **_kwargs: Mock(
            spec=UserCredentials
        )

        creds1 = self.client._get_impersonate_credentials(
            user_email=TEST_USER_EMAIL, scopes=GOOGLE_USER_SCOPES_LIST
        )
        creds2 = self.client._get_impersonate_credentials(
            user_email=TEST_USER_EMAIL, scopes=list(reversed(GOOGLE_USER_SCOPES_LIST))
        )

        self.assertIs(creds1, creds2)
        mock_impersonated_creds.assert_called_once()

    @patch("backend.common.google_client.default")
    @patch("backend.common.google_client.ImpersonatedCredentials")
    def test_omitted_scopes_reuse_the_default_scope_entry(
        self, mock_impersonated_creds, mock_default
    ):
        """Omitting scopes asks for the default set, not for a second entry."""

        mock_default.return_value = (self.mock_credentials, TEST_PROJECT_NAME)
        mock_impersonated_creds.side_effect = lambda **_kwargs: Mock(
            spec=UserCredentials
        )

        creds1 = self.client._get_impersonate_credentials(user_email=TEST_USER_EMAIL)
        creds2 = self.client._get_impersonate_credentials(
            user_email=TEST_USER_EMAIL, scopes=GOOGLE_USER_SCOPES_LIST
        )

        self.assertIs(creds1, creds2)
        mock_impersonated_creds.assert_called_once()

    @patch("backend.common.google_client.default")
    @patch("backend.common.google_client.ImpersonatedCredentials")
    def test_failed_impersonation_caches_nothing(
        self, mock_impersonated_creds, mock_default
    ):
        """A failed exchange must not leave the un-impersonated ADC credentials behind."""

        mock_default.return_value = (self.mock_credentials, TEST_PROJECT_NAME)
        mock_impersonated_creds.side_effect = [
            Exception("Auth failed"),
            self.mock_impersonated_credentials,
        ]

        with self.assertRaises(ValueError):
            self.client._get_impersonate_credentials(user_email=TEST_USER_EMAIL)

        self.assertEqual(self.client._credentials, {})

        creds = self.client._get_impersonate_credentials(user_email=TEST_USER_EMAIL)

        self.assertIs(creds, self.mock_impersonated_credentials)

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
        # The caller gets a per-thread resource that forwards to the service.
        self.assertIs(client_instance.events, self.mock_service.events)

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


class TestCreateMeetSpacesClient(TestCase):
    def setUp(self):
        env = {
            "USER_EMAIL": TEST_USER_EMAIL,
            "SERVICE_ACCOUNT_EMAIL": TEST_SERVICE_ACCOUNT_EMAIL,
            "ADMIN_EMAIL": TEST_ADMIN_EMAIL,
        }
        self.env_patcher = patch.dict(os.environ, env)
        self.env_patcher.start()

        self.mock_logger = Mock()
        self.mock_retry_utils = Mock(spec=MockRetryUtils)

        def mock_retry_caller(func):
            return func()

        self.mock_retry_utils.get_retry_on_transient.side_effect = mock_retry_caller

        self.client = GoogleClient(
            logger=self.mock_logger,
            retry_utils=self.mock_retry_utils,
        )
        self.mock_credentials = Mock(spec=UserCredentials)

    def tearDown(self):
        self.env_patcher.stop()

    @patch("backend.common.google_client.meet_v2")
    @patch.object(GoogleClient, "_get_impersonate_credentials")
    def test_create_meet_spaces_client_success(self, mock_get_creds, mock_meet_v2):
        """Returns a SpacesServiceAsyncClient built with impersonated credentials."""
        mock_get_creds.return_value = self.mock_credentials
        mock_client_instance = Mock()
        mock_meet_v2.SpacesServiceAsyncClient.return_value = mock_client_instance

        result = self.client.create_meet_spaces_client()

        self.mock_retry_utils.get_retry_on_transient.assert_called_once()
        mock_meet_v2.SpacesServiceAsyncClient.assert_called_once_with(
            credentials=self.mock_credentials,
        )
        self.assertIs(result, mock_client_instance)
        self.mock_logger.info.assert_called_once()

    @patch.object(GoogleClient, "_get_impersonate_credentials")
    def test_create_meet_spaces_client_no_credentials_raises(self, mock_get_creds):
        """Raises ValueError when credentials cannot be obtained."""
        mock_get_creds.return_value = None

        with self.assertRaises(ValueError) as cm:
            self.client.create_meet_spaces_client()

        self.assertIn("Credentials are not available", str(cm.exception))


class TestGoogleClientThreadSafety(TestCase):
    """Tests that concurrent callers never share one API service."""

    def setUp(self):
        env = {
            "USER_EMAIL": TEST_USER_EMAIL,
            "SERVICE_ACCOUNT_EMAIL": TEST_SERVICE_ACCOUNT_EMAIL,
            "ADMIN_EMAIL": TEST_ADMIN_EMAIL,
        }
        self.env_patcher = patch.dict(os.environ, env)
        self.env_patcher.start()

        self.mock_retry_utils = Mock(spec=MockRetryUtils)
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda func: func()

        self.client = GoogleClient(
            logger=Mock(),
            retry_utils=self.mock_retry_utils,
        )

    def tearDown(self):
        self.env_patcher.stop()

    def _call_from_threads(self, api_client):
        """Have THREAD_COUNT threads call through api_client at the same time."""
        barrier = threading.Barrier(THREAD_COUNT)

        def call():
            barrier.wait()
            return api_client.events().list(calendarId="primary").execute()

        with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
            return [
                future.result()
                for future in [pool.submit(call) for _ in range(THREAD_COUNT)]
            ]

    @patch("backend.common.google_client.build")
    @patch.object(GoogleClient, "_get_impersonate_credentials")
    def test_concurrent_calls_never_enter_one_service_together(
        self, mock_get_creds, mock_build
    ):
        """Threads calling at once must not meet inside a single service."""
        mock_get_creds.return_value = Mock(spec=UserCredentials)
        conflicts = []
        mock_build.side_effect = lambda *_args, **_kwargs: ConcurrencyProbeService(
            conflicts
        )

        api_client = self.client.create_calendar_client()
        self._call_from_threads(api_client)

        self.assertEqual(conflicts, [])

    @patch("backend.common.google_client.build")
    @patch.object(GoogleClient, "_get_impersonate_credentials")
    def test_each_calling_thread_builds_its_own_service(
        self, mock_get_creds, mock_build
    ):
        """Every thread resolves its own service, plus one for the creating thread."""
        mock_get_creds.return_value = Mock(spec=UserCredentials)
        mock_build.side_effect = lambda *_args, **_kwargs: ConcurrencyProbeService([])

        api_client = self.client.create_calendar_client()
        self._call_from_threads(api_client)

        self.assertEqual(mock_build.call_count, THREAD_COUNT + 1)

    @patch("backend.common.google_client.build")
    @patch.object(GoogleClient, "_get_impersonate_credentials")
    def test_repeated_calls_on_one_thread_reuse_one_service(
        self, mock_get_creds, mock_build
    ):
        """A thread keeps its service across calls instead of rebuilding it."""
        mock_get_creds.return_value = Mock(spec=UserCredentials)
        mock_build.side_effect = lambda *_args, **_kwargs: ConcurrencyProbeService([])

        api_client = self.client.create_calendar_client()
        api_client.events().list(calendarId="primary").execute()
        api_client.events().list(calendarId="primary").execute()

        self.assertEqual(mock_build.call_count, 1)

    @patch("backend.common.google_client.build")
    @patch("backend.common.google_client.default")
    @patch("backend.common.google_client.ImpersonatedCredentials")
    def test_each_calling_thread_impersonates_its_own_credentials(
        self, mock_impersonated_creds, mock_default, mock_build
    ):
        """Credentials hold a mutable token, so threads must not share one."""
        mock_default.return_value = (Mock(spec=ServiceAccountCredentials), "project")
        mock_impersonated_creds.side_effect = lambda **_kwargs: Mock(
            spec=UserCredentials
        )
        mock_build.side_effect = lambda *_args, **_kwargs: ConcurrencyProbeService([])

        api_client = self.client.create_calendar_client()
        self._call_from_threads(api_client)

        self.assertEqual(mock_impersonated_creds.call_count, THREAD_COUNT + 1)


if __name__ == "__main__":
    main()
