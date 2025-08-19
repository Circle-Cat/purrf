from unittest import TestCase, main
from unittest.mock import patch, Mock
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google.cloud.pubsub_v1 import SubscriberClient, PublisherClient
from backend.common.environment_constants import (
    USER_EMAIL,
    SERVICE_ACCOUNT_EMAIL,
    ADMIN_EMAIL,
)
from backend.common.google_client import GoogleClientFactory
from backend.common.logger import get_logger
import os

logger = get_logger()

TEST_PROJECT_NAME = "test-project"
TEST_USER_EMAIL = "test@example.com"
TEST_SERVICE_ACCOUNT_EMAIL = "test-service-account@project.iam.gserviceaccount.com"
TEST_ADMIN_EMAIL = "admin@example.com"
CLIENT_CONFIGS = [
    ("create_chat_client", "chat", "v1", "_chat_client"),
    ("create_people_client", "people", "v1", "_people_client"),
    (
        "create_workspaceevents_client",
        "workspaceevents",
        "v1",
        "_workspaceevents_client",
    ),
    ("create_calendar_client", "calendar", "v3", "_calendar_client"),
    ("create_reports_client", "admin", "reports_v1", "_reports_client"),
]

ENV_VAR_TEST_CASES = [
    ([USER_EMAIL], USER_EMAIL),
    ([SERVICE_ACCOUNT_EMAIL], SERVICE_ACCOUNT_EMAIL),
    ([USER_EMAIL, SERVICE_ACCOUNT_EMAIL], USER_EMAIL),
]


class TestGoogleClientFactory(TestCase):
    def _reset_google_client_factory(self):
        GoogleClientFactory._instance = None
        GoogleClientFactory._credentials = None
        GoogleClientFactory._chat_client = None
        GoogleClientFactory._people_client = None
        GoogleClientFactory._workspaceevents_client = None
        GoogleClientFactory._subscriber_client = None
        GoogleClientFactory._publisher_client = None
        GoogleClientFactory._calendar_client = None

    def test_client_creation_flow(self):
        for function_name, api_name, api_version, cache_attr in CLIENT_CONFIGS:
            self._reset_google_client_factory()
            with (
                self.subTest(function_name=function_name),
                patch("backend.common.google_client.default") as mock_default,
                patch(
                    "backend.common.google_client.ImpersonatedCredentials"
                ) as mock_impersonated_creds,
                patch("backend.common.google_client.build") as mock_build,
                patch.dict(
                    os.environ,
                    {
                        USER_EMAIL: TEST_USER_EMAIL,
                        SERVICE_ACCOUNT_EMAIL: TEST_SERVICE_ACCOUNT_EMAIL,
                        ADMIN_EMAIL: TEST_ADMIN_EMAIL,
                    },
                ),
            ):
                mock_credentials = Mock(spec=ServiceAccountCredentials)
                mock_impersonated_credentials = Mock(spec=UserCredentials)
                mock_service = Mock()

                mock_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
                mock_impersonated_creds.return_value = mock_impersonated_credentials
                mock_build.return_value = mock_service

                factory = GoogleClientFactory()
                create_method = getattr(factory, function_name)
                client = create_method()

                mock_default.assert_called_once()
                mock_impersonated_creds.assert_called_once()
                mock_build.assert_called_once_with(
                    api_name, api_version, credentials=mock_impersonated_credentials
                )
                self.assertIs(getattr(factory, cache_attr), mock_service)
                self.assertEqual(client, mock_service)

    def test_client_caching(self):
        for function_name, api_name, api_version, cache_attr in CLIENT_CONFIGS:
            self._reset_google_client_factory()
            with (
                self.subTest(function_name=function_name),
                patch("backend.common.google_client.default") as mock_default,
                patch(
                    "backend.common.google_client.ImpersonatedCredentials"
                ) as mock_impersonated_creds,
                patch("backend.common.google_client.build") as mock_build,
                patch.dict(
                    os.environ,
                    {
                        USER_EMAIL: TEST_USER_EMAIL,
                        SERVICE_ACCOUNT_EMAIL: TEST_SERVICE_ACCOUNT_EMAIL,
                        ADMIN_EMAIL: TEST_ADMIN_EMAIL,
                    },
                ),
            ):
                mock_credentials = Mock(spec=ServiceAccountCredentials)
                mock_impersonated_credentials = Mock(spec=UserCredentials)
                mock_service = Mock()

                mock_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
                mock_impersonated_creds.return_value = mock_impersonated_credentials
                mock_build.return_value = mock_service

                factory = GoogleClientFactory()
                create_method = getattr(factory, function_name)
                client1 = create_method()
                client2 = create_method()

                mock_default.assert_called_once()
                mock_impersonated_creds.assert_called_once()
                mock_build.assert_called_once_with(
                    api_name, api_version, credentials=mock_impersonated_credentials
                )
                self.assertIs(getattr(factory, cache_attr), mock_service)
                self.assertEqual(client1, mock_service)
                self.assertIs(client1, client2)
                self.assertEqual(mock_build.call_count, 1)

    def test_retry_mechanism(self):
        for function_name, api_name, api_version, cache_attr in CLIENT_CONFIGS:
            self._reset_google_client_factory()
            with (
                self.subTest(function_name=function_name),
                patch.dict(
                    os.environ,
                    {
                        USER_EMAIL: TEST_USER_EMAIL,
                        SERVICE_ACCOUNT_EMAIL: TEST_SERVICE_ACCOUNT_EMAIL,
                        ADMIN_EMAIL: TEST_ADMIN_EMAIL,
                    },
                ),
                patch("backend.common.google_client.default") as mock_default,
                patch(
                    "backend.common.google_client.ImpersonatedCredentials"
                ) as mock_impersonated_creds,
                patch("backend.common.google_client.build") as mock_build,
            ):
                mock_credentials = Mock(spec=ServiceAccountCredentials)
                mock_impersonated_credentials = Mock(spec=UserCredentials)

                mock_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
                mock_impersonated_creds.return_value = mock_impersonated_credentials
                mock_build.side_effect = [Exception, Mock()]

                factory = GoogleClientFactory()
                _ = getattr(factory, function_name)()

                self.assertEqual(mock_build.call_count, 2)

    def test_missing_environment_variables(self):
        for missing_vars, expected_var in ENV_VAR_TEST_CASES:
            self._reset_google_client_factory()
            with (
                self.subTest(missing_vars=missing_vars),
                patch.dict(os.environ, clear=True) as mock_env,
                patch("backend.common.google_client.default") as mock_default,
            ):
                if USER_EMAIL not in missing_vars:
                    mock_env[USER_EMAIL] = TEST_USER_EMAIL
                if SERVICE_ACCOUNT_EMAIL not in missing_vars:
                    mock_env[SERVICE_ACCOUNT_EMAIL] = TEST_SERVICE_ACCOUNT_EMAIL
                if ADMIN_EMAIL not in missing_vars:
                    mock_env[ADMIN_EMAIL] = TEST_ADMIN_EMAIL

                mock_credentials = Mock(spec=ServiceAccountCredentials)
                mock_default.return_value = (mock_credentials, TEST_PROJECT_NAME)

                factory = GoogleClientFactory()

                with self.assertRaises(ValueError) as cm:
                    factory.create_chat_client()

                self.assertIn(expected_var, str(cm.exception))

    @patch("backend.common.google_client.SubscriberClient")
    def test_create_subscriber_client(self, mock_subscriber_client):
        self._reset_google_client_factory()
        mock_subscriber_instance = Mock(spec=SubscriberClient)
        mock_subscriber_client.return_value = mock_subscriber_instance

        factory = GoogleClientFactory()

        subscriber_client1 = factory.create_subscriber_client()
        mock_subscriber_client.assert_called_once()
        self.assertIs(subscriber_client1, mock_subscriber_instance)

        subscriber_client2 = factory.create_subscriber_client()
        self.assertIs(subscriber_client1, subscriber_client2)
        self.assertEqual(mock_subscriber_client.call_count, 1)

    @patch("backend.common.google_client.PublisherClient")
    def test_create_publisher_client(self, mock_publisher_client):
        self._reset_google_client_factory()
        mock_publisher_instance = Mock(spec=PublisherClient)
        mock_publisher_client.return_value = mock_publisher_instance

        factory = GoogleClientFactory()

        publisher_client1 = factory.create_publisher_client()
        mock_publisher_client.assert_called_once()
        self.assertIs(publisher_client1, mock_publisher_instance)

        publisher_client2 = factory.create_publisher_client()
        self.assertIs(publisher_client1, publisher_client2)
        self.assertEqual(mock_publisher_client.call_count, 1)


if __name__ == "__main__":
    main()
