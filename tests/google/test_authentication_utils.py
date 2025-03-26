import unittest
from unittest.mock import Mock, patch
import logging
from tools.log.logger import setup_logger
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google.cloud.pubsub_v1 import SubscriberClient
from io import StringIO
import os
from google.constants import (
    CHAT_API_NAME,
    CHAT_API_VERSION,
    PEOPLE_API_NAME,
    PEOPLE_API_VERSION,
    CREDENTIALS_SUCCESS_MSG,
    SERVICE_CREATED_MSG,
    USING_CREDENTIALS_MSG,
    NO_CREDENTIALS_ERROR_MSG,
    USER_EMAIL,
)
from google.authentication_utils import GoogleClientFactory

TEST_PROJECT_NAME = "test-project"
TEST_BUILD_FAILED_MSG = "Build failed"
TEST_USER_EMAIL = "test@example.com"
TEST_IMPERSONATED_CREDENTIALS = "impersonated_credentials"


class TestExceptionHandler(unittest.TestCase):
    def setUp(self):
        GoogleClientFactory._instance = None
        GoogleClientFactory._credentials = None
        GoogleClientFactory._chat_client = None
        GoogleClientFactory._people_client = None
        GoogleClientFactory._subscriber_client = None

    @patch("google.authentication_utils.default")
    @patch.dict(os.environ, {USER_EMAIL: TEST_USER_EMAIL})
    def test_get_credentials_impersonate(self, mock_auth_default):
        mock_service_account_credentials = Mock(spec=ServiceAccountCredentials)
        mock_with_subject = Mock(return_value=TEST_IMPERSONATED_CREDENTIALS)
        mock_service_account_credentials.with_subject = mock_with_subject
        mock_auth_default.return_value = (
            mock_service_account_credentials,
            TEST_PROJECT_NAME,
        )

        factory = GoogleClientFactory()
        result = factory._get_credentials()

        self.assertEqual(result, TEST_IMPERSONATED_CREDENTIALS)
        mock_auth_default.assert_called_once()
        mock_with_subject.assert_called_once_with(TEST_USER_EMAIL)

    @patch("google.authentication_utils.default")
    def test_get_credentials_user(self, mock_auth_default):
        mock_credentials = Mock(spec=UserCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)

        factory = GoogleClientFactory()
        result = factory._get_credentials()

        self.assertEqual(result, mock_credentials)
        mock_auth_default.assert_called_once()
        second_result = factory._get_credentials()
        self.assertEqual(second_result, mock_credentials)
        self.assertEqual(mock_auth_default.call_count, 1)

    @patch("google.authentication_utils.default")
    def test_get_credentials_other(self, mock_auth_default):
        mock_credentials = Mock()
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)

        factory = GoogleClientFactory()
        result = factory._get_credentials()

        self.assertEqual(result, mock_credentials)
        mock_auth_default.assert_called_once()
        second_result = factory._get_credentials()
        self.assertEqual(second_result, mock_credentials)
        self.assertEqual(mock_auth_default.call_count, 1)

    @patch("google.authentication_utils.default")
    def test_get_credentials_none(self, mock_auth_default):
        mock_auth_default.return_value = (None, None)

        factory = GoogleClientFactory()
        result = factory._get_credentials()

        self.assertIsNone(result)
        mock_auth_default.assert_called_once()

    @patch("google.authentication_utils.default")
    @patch("google.authentication_utils.build")
    def test_create_client_success(self, mock_build, mock_auth_default):
        mock_credentials = Mock(spec=ServiceAccountCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
        mock_service = Mock()
        mock_build.return_value = mock_service

        factory = GoogleClientFactory()
        result = factory._create_client(CHAT_API_NAME, CHAT_API_VERSION)

        self.assertEqual(result, mock_service)
        mock_auth_default.assert_called_once()
        mock_build.assert_called_once_with(
            CHAT_API_NAME, CHAT_API_VERSION, credentials=mock_credentials
        )

    @patch("google.authentication_utils.default")
    @patch("google.authentication_utils.build")
    def test_create_client_no_credentials(self, mock_build, mock_auth_default):
        mock_auth_default.return_value = (None, None)

        factory = GoogleClientFactory()
        result = factory._create_client(CHAT_API_NAME, CHAT_API_VERSION)

        self.assertIsNone(result)
        mock_auth_default.assert_called_once()
        mock_build.assert_not_called()

    @patch("google.authentication_utils.build")
    @patch("google.authentication_utils.default")
    def test_create_chat_client_success(self, mock_auth_default, mock_build):
        mock_credentials = Mock(spec=ServiceAccountCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
        mock_service = Mock()
        mock_build.return_value = mock_service

        factory = GoogleClientFactory()
        result = factory.create_chat_client()

        self.assertEqual(result, mock_service)
        mock_auth_default.assert_called_once()
        mock_build.assert_called_once_with(
            CHAT_API_NAME, CHAT_API_VERSION, credentials=mock_credentials
        )

        second_result = factory.create_chat_client()
        self.assertEqual(second_result, mock_service)
        self.assertEqual(mock_build.call_count, 1)

    @patch("google.authentication_utils.build")
    @patch("google.authentication_utils.default")
    def test_create_people_client_success(self, mock_auth_default, mock_build):
        mock_credentials = Mock(spec=ServiceAccountCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
        mock_service = Mock()
        mock_build.return_value = mock_service

        factory = GoogleClientFactory()
        result = factory.create_people_client()

        self.assertEqual(result, mock_service)
        mock_auth_default.assert_called_once()
        mock_build.assert_called_once_with(
            PEOPLE_API_NAME, PEOPLE_API_VERSION, credentials=mock_credentials
        )

        second_result = factory.create_people_client()
        self.assertEqual(second_result, mock_service)
        self.assertEqual(mock_build.call_count, 1)

    @patch("google.authentication_utils.build")
    @patch("google.authentication_utils.default")
    def test_create_client_build_exception(self, mock_auth_default, mock_build):
        mock_credentials = Mock(spec=ServiceAccountCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
        mock_build.side_effect = Exception(TEST_BUILD_FAILED_MSG)

        factory = GoogleClientFactory()

        with self.assertRaises(Exception) as context:
            factory._create_client(CHAT_API_NAME, CHAT_API_VERSION)
        self.assertEqual(str(context.exception), TEST_BUILD_FAILED_MSG)
        mock_auth_default.assert_called_once()
        mock_build.assert_called_once_with(
            CHAT_API_NAME, CHAT_API_VERSION, credentials=mock_credentials
        )

    @patch("google.authentication_utils.build")
    @patch("google.authentication_utils.default")
    def test_singleton_behavior(self, mock_auth_default, mock_build):
        mock_credentials = Mock(spec=ServiceAccountCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
        mock_service = Mock()
        mock_build.return_value = mock_service

        factory1 = GoogleClientFactory()
        factory2 = GoogleClientFactory()

        self.assertIs(factory1, factory2)

        chat_client1 = factory1.create_chat_client()
        chat_client2 = factory2.create_chat_client()
        chat_client3 = factory1.create_chat_client()

        people_client = factory2.create_people_client()

        self.assertEqual(chat_client1, mock_service)
        self.assertEqual(chat_client2, mock_service)
        self.assertEqual(chat_client3, mock_service)
        self.assertIs(chat_client1, chat_client2)
        self.assertIs(chat_client2, chat_client3)

        self.assertEqual(people_client, mock_service)
        mock_auth_default.assert_called_once()
        mock_build.assert_any_call(
            CHAT_API_NAME, CHAT_API_VERSION, credentials=mock_credentials
        )
        mock_build.assert_any_call(
            PEOPLE_API_NAME, PEOPLE_API_VERSION, credentials=mock_credentials
        )
        self.assertEqual(mock_build.call_count, 2)

    @patch("google.authentication_utils.SubscriberClient")
    def test_create_subscriber_client_success(self, mock_subscriber_client):
        mock_client_instance = Mock()
        mock_subscriber_client.return_value = mock_client_instance

        factory = GoogleClientFactory()

        result = factory.create_subscriber_client()

        self.assertEqual(result, mock_client_instance)
        mock_subscriber_client.assert_called_once()
        second_result = factory.create_subscriber_client()
        self.assertEqual(second_result, mock_client_instance)
        self.assertEqual(mock_subscriber_client.call_count, 1)


if __name__ == "__main__":
    unittest.main()
