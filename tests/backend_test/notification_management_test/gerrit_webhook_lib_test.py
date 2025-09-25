import unittest
from unittest.mock import patch, MagicMock, call
import os

from backend.notification_management import gerrit_webhook_lib as script_to_test


class TestGerritWebhookLib(unittest.TestCase):
    _mock_env_vars = {
        "GERRIT_URL": "http://gerrit.example.com",
        "GERRIT_USER": "test_user",
        "GERRIT_HTTP_PASS": "test_pass",
        "GERRIT_WEBHOOK_TARGET_URL": "http://target.example.com/webhook",
        "GERRIT_WEBHOOK_REMOTE_NAME": "test-webhook",
        "GERRIT_WEBHOOK_EVENTS": "patchset-created,change-merged",
        "GERRIT_WEBHOOK_SECRET": "super_secret",
        "GERRIT_WEBHOOK_PROJECT": "test-project",
    }

    @patch("os.getenv")
    def test_require_env_present(self, mock_getenv):
        mock_getenv.return_value = "value"
        self.assertEqual(script_to_test.require_env("TEST_VAR"), "value")
        mock_getenv.assert_called_once_with("TEST_VAR", None)

    @patch("os.getenv")
    def test_require_env_missing_no_default(self, mock_getenv):
        mock_getenv.return_value = None
        with self.assertRaisesRegex(
            ValueError, "Missing required environment variable: TEST_VAR"
        ):
            script_to_test.require_env("TEST_VAR")
        mock_getenv.assert_called_once_with("TEST_VAR", None)

    @patch("os.getenv")
    def test_require_env_missing_with_default(self, mock_getenv):
        mock_getenv.return_value = None
        self.assertEqual(
            script_to_test.require_env("TEST_VAR", default="default_value"),
            "default_value",
        )
        mock_getenv.assert_called_once_with("TEST_VAR", "default_value")

    def test_validate_url_valid(self):
        self.assertEqual(
            script_to_test.validate_url("http://valid.com", "VAR"), "http://valid.com"
        )
        self.assertEqual(
            script_to_test.validate_url("https://valid.com/path?q=1", "VAR"),
            "https://valid.com/path?q=1",
        )

    def test_validate_url_invalid(self):
        with self.assertRaisesRegex(ValueError, "Invalid URL in VAR: invalid-url"):
            script_to_test.validate_url("invalid-url", "VAR")
        with self.assertRaisesRegex(ValueError, "Invalid URL in VAR: http://"):
            script_to_test.validate_url("http://", "VAR")
        with self.assertRaisesRegex(ValueError, "Invalid URL in VAR: //host"):
            script_to_test.validate_url("//host", "VAR")

    @patch(
        "backend.notification_management.gerrit_subscription_service.GerritSubscriptionService"
    )
    @patch("backend.common.gerrit_client.GerritClient")
    @patch("backend.common.logger.get_logger")
    @patch.dict(os.environ, _mock_env_vars, clear=True)
    def test_run_gerrit_webhook_registration_success(
        self, mock_get_logger, MockGerritClient, MockGerritSubscriptionService
    ):
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        mock_gerrit_client_instance = MockGerritClient.return_value
        mock_gerrit_subscription_service_instance = (
            MockGerritSubscriptionService.return_value
        )
        expected_result = {"status": "registered"}
        mock_gerrit_subscription_service_instance.register_webhook.return_value = (
            expected_result
        )

        result = script_to_test.run_gerrit_webhook_registration()

        self.assertEqual(result, expected_result)

        mock_get_logger.assert_called_once()
        mock_logger_instance.info.assert_has_calls([
            call(unittest.mock.ANY),
            call(f"Webhook registration result: {expected_result}"),
        ])

        MockGerritClient.assert_called_once_with(
            base_url="http://gerrit.example.com",
            username="test_user",
            http_password="test_pass",
        )

        MockGerritSubscriptionService.assert_called_once_with(
            logger=mock_logger_instance,
            gerrit_client=mock_gerrit_client_instance,
            project="test-project",
            remote_name="test-webhook",
            subscribe_url="http://target.example.com/webhook",
            secret="super_secret",
            events=["patchset-created", "change-merged"],
        )

        mock_gerrit_subscription_service_instance.register_webhook.assert_called_once()

    @patch("backend.common.logger.get_logger")
    @patch.dict(os.environ, {}, clear=True)
    def test_run_gerrit_webhook_registration_missing_gerrit_url(self, mock_get_logger):
        with self.assertRaisesRegex(
            ValueError, "Missing required environment variable: GERRIT_URL"
        ):
            script_to_test.run_gerrit_webhook_registration()

    @patch("backend.common.logger.get_logger")
    @patch.dict(
        os.environ,
        {
            "GERRIT_URL": "invalid-url",
            "GERRIT_USER": "test_user",
            "GERRIT_HTTP_PASS": "test_pass",
            "GERRIT_WEBHOOK_TARGET_URL": "http://target.example.com/webhook",
            "GERRIT_WEBHOOK_EVENTS": "patchset-created",
        },
        clear=True,
    )
    def test_run_gerrit_webhook_registration_invalid_gerrit_url(self, mock_get_logger):
        with self.assertRaisesRegex(
            ValueError, "Invalid URL in GERRIT_URL: invalid-url"
        ):
            script_to_test.run_gerrit_webhook_registration()

    @patch("backend.common.logger.get_logger")
    @patch.dict(os.environ, _mock_env_vars, clear=True)
    def test_run_gerrit_webhook_registration_empty_events(self, mock_get_logger):
        mock_env_with_empty_events = self._mock_env_vars.copy()
        mock_env_with_empty_events["GERRIT_WEBHOOK_EVENTS"] = ""

        with patch.dict(os.environ, mock_env_with_empty_events, clear=True):
            with self.assertRaisesRegex(
                ValueError, "No valid events configured for webhook"
            ):
                script_to_test.run_gerrit_webhook_registration()

    @patch(
        "backend.notification_management.gerrit_subscription_service.GerritSubscriptionService"
    )
    @patch("backend.common.gerrit_client.GerritClient")
    @patch("backend.common.logger.get_logger")
    @patch.dict(
        os.environ,
        {
            "GERRIT_URL": "http://gerrit.example.com",
            "GERRIT_USER": "test_user",
            "GERRIT_HTTP_PASS": "test_pass",
            "GERRIT_WEBHOOK_TARGET_URL": "http://target.example.com/webhook",
        },
        clear=True,
    )
    def test_run_gerrit_webhook_registration_default_values(
        self, mock_get_logger, MockGerritClient, MockGerritSubscriptionService
    ):
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        mock_gerrit_client_instance = MockGerritClient.return_value
        mock_gerrit_subscription_service_instance = (
            MockGerritSubscriptionService.return_value
        )
        expected_result = {"status": "registered_default"}
        mock_gerrit_subscription_service_instance.register_webhook.return_value = (
            expected_result
        )

        result = script_to_test.run_gerrit_webhook_registration()

        self.assertEqual(result, expected_result)

        mock_get_logger.assert_called_once()
        mock_logger_instance.info.assert_has_calls([
            call(unittest.mock.ANY),
            call(f"Webhook registration result: {expected_result}"),
        ])

        MockGerritClient.assert_called_once_with(
            base_url="http://gerrit.example.com",
            username="test_user",
            http_password="test_pass",
        )

        default_events_string = "patchset-created,change-merged,change-abandoned,comment-added,change-restored,project-created"
        expected_default_events = [
            e.strip() for e in default_events_string.split(",") if e.strip()
        ]

        MockGerritSubscriptionService.assert_called_once_with(
            logger=mock_logger_instance,
            gerrit_client=mock_gerrit_client_instance,
            project="All-Projects",
            remote_name="gerrit-webhook",
            subscribe_url="http://target.example.com/webhook",
            secret=None,
            events=expected_default_events,
        )
        mock_gerrit_subscription_service_instance.register_webhook.assert_called_once()
