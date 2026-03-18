from unittest import TestCase, main
from unittest.mock import patch, Mock, MagicMock
from backend.common.launchdarkly_client import LaunchDarklyClient
from backend.common.environment_constants import LAUNCHDARKLY_SDK_KEY
from backend.dto.user_context_dto import UserContextDto
import os


class TestLaunchDarklyClientInit(TestCase):
    def test_init_stores_logger_and_no_client(self):
        logger = Mock()
        client = LaunchDarklyClient(logger)

        self.assertEqual(client.logger, logger)
        self.assertIsNone(client._client)


class TestLaunchDarklyClientInitialize(TestCase):
    @patch("backend.common.launchdarkly_client.ldclient")
    @patch.dict(os.environ, {}, clear=True)
    def test_offline_mode_when_sdk_key_not_set(self, mock_ldclient):
        logger = Mock()
        client = LaunchDarklyClient(logger)
        client.initialize()

        logger.warning.assert_called_once()
        mock_ldclient.set_config.assert_called_once()
        self.assertEqual(client._client, mock_ldclient.get.return_value)

    @patch("backend.common.launchdarkly_client.ldclient")
    @patch.dict(os.environ, {LAUNCHDARKLY_SDK_KEY: "sdk-test-key"})
    def test_initialized_successfully(self, mock_ldclient):
        mock_ldclient.get.return_value.is_initialized.return_value = True
        logger = Mock()

        client = LaunchDarklyClient(logger)
        client.initialize()

        logger.info.assert_called_once()
        self.assertEqual(client._client, mock_ldclient.get.return_value)

    @patch("backend.common.launchdarkly_client.ldclient")
    @patch.dict(os.environ, {LAUNCHDARKLY_SDK_KEY: "sdk-test-key"})
    def test_initialization_failure_logs_error(self, mock_ldclient):
        mock_ldclient.get.return_value.is_initialized.return_value = False
        logger = Mock()

        client = LaunchDarklyClient(logger)
        client.initialize()

        logger.error.assert_called_once()


class TestLaunchDarklyClientVariation(TestCase):
    @patch("backend.common.launchdarkly_client.ldclient")
    @patch.dict(os.environ, {LAUNCHDARKLY_SDK_KEY: "sdk-test-key"})
    def setUp(self, mock_ldclient):
        self.mock_ldclient = mock_ldclient
        self.mock_ld_instance = MagicMock()
        self.mock_ld_instance.is_initialized.return_value = True
        mock_ldclient.get.return_value = self.mock_ld_instance
        self.client = LaunchDarklyClient(Mock())
        self.client.initialize()

    def test_variation_returns_flag_value(self):
        self.mock_ld_instance.variation.return_value = True
        user_context = UserContextDto(sub="user-123", primary_email="test@example.com")

        result = self.client.variation("feature-flag", user_context, False)

        self.assertTrue(result)
        self.mock_ld_instance.variation.assert_called_once()

    def test_variation_returns_default_when_sub_missing(self):
        user_context = UserContextDto(sub=None, primary_email=None)

        result = self.client.variation("feature-flag", user_context, "default")

        self.assertEqual(result, "default")
        self.mock_ld_instance.variation.assert_not_called()

    def test_variation_returns_default_when_not_initialized(self):
        logger = Mock()
        client = LaunchDarklyClient(logger)
        user_context = UserContextDto(sub="user-123", primary_email="test@example.com")

        result = client.variation("feature-flag", user_context, "default")

        self.assertEqual(result, "default")
        logger.warning.assert_called_once()


class TestLaunchDarklyClientClose(TestCase):
    @patch("backend.common.launchdarkly_client.ldclient")
    @patch.dict(os.environ, {LAUNCHDARKLY_SDK_KEY: "sdk-test-key"})
    def test_close_shuts_down_client(self, mock_ldclient):
        mock_instance = MagicMock()
        mock_instance.is_initialized.return_value = True
        mock_ldclient.get.return_value = mock_instance

        client = LaunchDarklyClient(Mock())
        client.initialize()
        client.close()

        mock_instance.close.assert_called_once()

    def test_close_does_nothing_when_not_initialized(self):
        client = LaunchDarklyClient(Mock())
        client.close()  # Should not raise


if __name__ == "__main__":
    main()
