import unittest
from unittest.mock import Mock, patch
import logging
from tools.log.logger import setup_logger
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from io import StringIO
from google.constants import (
    CHAT_API_NAME,
    CHAT_API_VERSION,
    PEOPLE_API_NAME,
    PEOPLE_API_VERSION,
    CREDENTIALS_SUCCESS_MSG,
    USING_SERVICE_ACCOUNT_CREDENTIALS_MSG,
    NO_CREDENTIALS_ERROR_MSG,
    SERVICE_CREATED_MSG,
    USING_USER_CREDENTIALS_MSG,
    USING_OTHER_CREDENTIALS_MSG,
)

TEST_PROJECT_NAME = "test-project"
TEST_BUILD_FAILED_MSG = "Build failed"


class TestExceptionHandler(unittest.TestCase):
    def setUp(self):
        self.log_capture_string = StringIO()
        ch = logging.StreamHandler(self.log_capture_string)
        setup_logger()
        root_logger = logging.getLogger()
        ch.setFormatter(root_logger.handlers[0].formatter)
        logging.getLogger().addHandler(ch)

        from google.authentication_utils import GoogleClientFactory

        GoogleClientFactory._instance = None
        GoogleClientFactory._credentials = None
        GoogleClientFactory._chat_client = None
        GoogleClientFactory._people_client = None

    def tearDown(self):
        logging.getLogger().handlers = []

    @patch("google.authentication_utils.default")
    def test_get_credentials_user(self, mock_auth_default):
        mock_credentials = Mock(spec=UserCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)

        from google.authentication_utils import GoogleClientFactory

        factory = GoogleClientFactory()
        result = factory._get_credentials()

        self.assertEqual(result, mock_credentials)
        mock_auth_default.assert_called_once()
        log_output = self.log_capture_string.getvalue()
        self.assertIn(
            CREDENTIALS_SUCCESS_MSG.format(project_id=TEST_PROJECT_NAME), log_output
        )
        self.assertIn(USING_USER_CREDENTIALS_MSG, log_output)
        self.assertNotIn(USING_SERVICE_ACCOUNT_CREDENTIALS_MSG, log_output)
        self.assertNotIn(
            USING_OTHER_CREDENTIALS_MSG.format(credentials_type=type(mock_credentials)),
            log_output,
        )

        second_result = factory._get_credentials()
        self.assertEqual(second_result, mock_credentials)
        self.assertEqual(mock_auth_default.call_count, 1)

    @patch("google.authentication_utils.default")
    def test_get_credentials_other(self, mock_auth_default):
        mock_credentials = Mock()
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)

        from google.authentication_utils import GoogleClientFactory

        factory = GoogleClientFactory()
        result = factory._get_credentials()

        self.assertEqual(result, mock_credentials)
        mock_auth_default.assert_called_once()
        log_output = self.log_capture_string.getvalue()
        self.assertIn(
            CREDENTIALS_SUCCESS_MSG.format(project_id=TEST_PROJECT_NAME), log_output
        )
        self.assertIn(
            USING_OTHER_CREDENTIALS_MSG.format(credentials_type=type(mock_credentials)),
            log_output,
        )
        self.assertNotIn(USING_SERVICE_ACCOUNT_CREDENTIALS_MSG, log_output)
        self.assertNotIn(USING_USER_CREDENTIALS_MSG, log_output)

        second_result = factory._get_credentials()
        self.assertEqual(second_result, mock_credentials)
        self.assertEqual(mock_auth_default.call_count, 1)

    @patch("google.authentication_utils.default")
    def test_get_credentials_none(self, mock_auth_default):
        mock_auth_default.return_value = (None, None)

        from google.authentication_utils import GoogleClientFactory

        factory = GoogleClientFactory()
        result = factory._get_credentials()

        self.assertIsNone(result)
        mock_auth_default.assert_called_once()
        log_output = self.log_capture_string.getvalue()
        self.assertIn(CREDENTIALS_SUCCESS_MSG.format(project_id=None), log_output)
        self.assertNotIn(USING_SERVICE_ACCOUNT_CREDENTIALS_MSG, log_output)
        self.assertNotIn(USING_USER_CREDENTIALS_MSG, log_output)
        self.assertNotIn(
            USING_OTHER_CREDENTIALS_MSG.format(credentials_type="NoneType"), log_output
        )

    @patch("google.authentication_utils.default")
    @patch("google.authentication_utils.build")
    def test_create_client_success(self, mock_build, mock_auth_default):
        mock_credentials = Mock(spec=ServiceAccountCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
        mock_service = Mock()
        mock_build.return_value = mock_service

        from google.authentication_utils import GoogleClientFactory

        factory = GoogleClientFactory()

        result = factory._create_client(CHAT_API_NAME, CHAT_API_VERSION)

        self.assertEqual(result, mock_service)
        mock_auth_default.assert_called_once()
        mock_build.assert_called_once_with(
            CHAT_API_NAME, CHAT_API_VERSION, credentials=mock_credentials
        )

        log_output = self.log_capture_string.getvalue()
        self.assertIn(
            CREDENTIALS_SUCCESS_MSG.format(project_id=TEST_PROJECT_NAME), log_output
        )
        self.assertIn(USING_SERVICE_ACCOUNT_CREDENTIALS_MSG, log_output)
        self.assertIn(SERVICE_CREATED_MSG.format(api_name=CHAT_API_NAME), log_output)

    @patch("google.authentication_utils.default")
    @patch("google.authentication_utils.build")
    def test_create_client_no_credentials(self, mock_build, mock_auth_default):
        mock_auth_default.return_value = (None, None)

        from google.authentication_utils import GoogleClientFactory

        factory = GoogleClientFactory()

        result = factory._create_client(CHAT_API_NAME, CHAT_API_VERSION)

        self.assertIsNone(result)
        mock_auth_default.assert_called_once()
        mock_build.assert_not_called()

        log_output = self.log_capture_string.getvalue()
        self.assertIn(NO_CREDENTIALS_ERROR_MSG, log_output)
        self.assertNotIn(SERVICE_CREATED_MSG.format(api_name=CHAT_API_NAME), log_output)

    @patch("google.authentication_utils.build")
    @patch("google.authentication_utils.default")
    def test_create_chat_client_success(self, mock_auth_default, mock_build):
        mock_credentials = Mock(spec=ServiceAccountCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
        mock_service = Mock()
        mock_build.return_value = mock_service

        from google.authentication_utils import GoogleClientFactory

        factory = GoogleClientFactory()

        result = factory.create_chat_client()

        self.assertEqual(result, mock_service)
        mock_auth_default.assert_called_once()
        mock_build.assert_called_once_with(
            CHAT_API_NAME, CHAT_API_VERSION, credentials=mock_credentials
        )
        log_output = self.log_capture_string.getvalue()
        self.assertIn(
            CREDENTIALS_SUCCESS_MSG.format(project_id=TEST_PROJECT_NAME), log_output
        )
        self.assertIn(USING_SERVICE_ACCOUNT_CREDENTIALS_MSG, log_output)
        self.assertIn(SERVICE_CREATED_MSG.format(api_name=CHAT_API_NAME), log_output)

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

        from google.authentication_utils import GoogleClientFactory

        factory = GoogleClientFactory()

        result = factory.create_people_client()

        self.assertEqual(result, mock_service)
        mock_auth_default.assert_called_once()
        mock_build.assert_called_once_with(
            PEOPLE_API_NAME, PEOPLE_API_VERSION, credentials=mock_credentials
        )
        log_output = self.log_capture_string.getvalue()
        self.assertIn(
            CREDENTIALS_SUCCESS_MSG.format(project_id=TEST_PROJECT_NAME), log_output
        )
        self.assertIn(USING_SERVICE_ACCOUNT_CREDENTIALS_MSG, log_output)
        self.assertIn(SERVICE_CREATED_MSG.format(api_name=PEOPLE_API_NAME), log_output)

        second_result = factory.create_people_client()
        self.assertEqual(second_result, mock_service)
        self.assertEqual(mock_build.call_count, 1)

    @patch("google.authentication_utils.build")
    @patch("google.authentication_utils.default")
    def test_create_client_build_exception(self, mock_auth_default, mock_build):
        mock_credentials = Mock(spec=ServiceAccountCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
        mock_build.side_effect = Exception(TEST_BUILD_FAILED_MSG)

        from google.authentication_utils import GoogleClientFactory

        factory = GoogleClientFactory()

        with self.assertRaises(Exception) as context:
            factory._create_client(CHAT_API_NAME, CHAT_API_VERSION)
        self.assertEqual(str(context.exception), TEST_BUILD_FAILED_MSG)
        mock_auth_default.assert_called_once()
        mock_build.assert_called_once_with(
            CHAT_API_NAME, CHAT_API_VERSION, credentials=mock_credentials
        )
        log_output = self.log_capture_string.getvalue()
        self.assertIn(
            CREDENTIALS_SUCCESS_MSG.format(project_id=TEST_PROJECT_NAME), log_output
        )
        self.assertNotIn(SERVICE_CREATED_MSG.format(api_name=CHAT_API_NAME), log_output)

    @patch("google.authentication_utils.build")
    @patch("google.authentication_utils.default")
    def test_singleton_behavior(self, mock_auth_default, mock_build):
        mock_credentials = Mock(spec=ServiceAccountCredentials)
        mock_auth_default.return_value = (mock_credentials, TEST_PROJECT_NAME)
        mock_service = Mock()
        mock_build.return_value = mock_service

        from google.authentication_utils import GoogleClientFactory

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
        log_output = self.log_capture_string.getvalue()
        self.assertEqual(
            log_output.count(
                CREDENTIALS_SUCCESS_MSG.format(project_id=TEST_PROJECT_NAME)
            ),
            1,
        )
        self.assertEqual(
            log_output.count(SERVICE_CREATED_MSG.format(api_name=CHAT_API_NAME)), 1
        )
        self.assertEqual(
            log_output.count(SERVICE_CREATED_MSG.format(api_name=PEOPLE_API_NAME)), 1
        )


if __name__ == "__main__":
    unittest.main()
