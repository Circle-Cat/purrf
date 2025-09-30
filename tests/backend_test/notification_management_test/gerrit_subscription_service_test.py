from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import MagicMock
from requests.exceptions import HTTPError

from backend.notification_management.gerrit_subscription_service import (
    GerritSubscriptionService,
)

# Constants for test data
TEST_PROJECT = "test-project"
TEST_REMOTE = "test-remote"
TEST_TARGET_URL = "http://example.com/webhook"
TEST_EVENTS_STR = "one,two,three"
TEST_EVENTS_LIST = TEST_EVENTS_STR.split(",")


class TestGerritSubscriptionService(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_session = MagicMock()
        self.fake_client = MagicMock(
            base_url="http://gerrit.example.com/", session=self.mock_session
        )
        self.service_kwargs = {
            "logger": self.mock_logger,
            "gerrit_client": self.fake_client,
            "project": TEST_PROJECT,
            "remote_name": TEST_REMOTE,
            "subscribe_url": TEST_TARGET_URL,
            "events": TEST_EVENTS_LIST,
        }

    def test_init_raises_value_error_for_missing_logger(self):
        kwargs = {**self.service_kwargs, "logger": None}
        with self.assertRaisesRegex(ValueError, "A valid logger instance is required."):
            GerritSubscriptionService(**kwargs)

    def test_init_raises_value_error_for_missing_gerrit_client(self):
        kwargs = {**self.service_kwargs, "gerrit_client": None}
        with self.assertRaisesRegex(
            ValueError, "A valid Gerrit client instance is required."
        ):
            GerritSubscriptionService(**kwargs)

    def test_init_raises_value_error_for_missing_project(self):
        kwargs = {**self.service_kwargs, "project": ""}
        with self.assertRaisesRegex(ValueError, "A valid project name is required."):
            GerritSubscriptionService(**kwargs)

    def test_init_raises_value_error_for_missing_remote_name(self):
        kwargs = {**self.service_kwargs, "remote_name": ""}
        with self.assertRaisesRegex(ValueError, "A valid remote name is required."):
            GerritSubscriptionService(**kwargs)

    def test_init_raises_value_error_for_missing_subscribe_url(self):
        kwargs = {**self.service_kwargs, "subscribe_url": ""}
        with self.assertRaisesRegex(ValueError, "A valid target URL is required."):
            GerritSubscriptionService(**kwargs)

    def test_init_raises_value_error_for_missing_events(self):
        kwargs = {**self.service_kwargs, "events": []}
        with self.assertRaisesRegex(ValueError, "At least one event is required."):
            GerritSubscriptionService(**kwargs)

    def test_register_webhook_success_and_secret_and_events(self):
        put_resp = MagicMock(status_code=HTTPStatus.CREATED)
        put_resp.json.return_value = {"status": "created"}
        self.mock_session.put.return_value = put_resp

        watcher = GerritSubscriptionService(**self.service_kwargs)
        result = watcher.register_webhook()

        expected_path = (
            f"/a/config/server/webhooks~projects/{TEST_PROJECT}/remotes/{TEST_REMOTE}"
        )
        expected_url = self.fake_client.base_url.rstrip("/") + expected_path
        self.mock_session.put.assert_called_once_with(
            expected_url,
            json={
                "url": TEST_TARGET_URL,
                "events": TEST_EVENTS_LIST,  # Corrected from TEST_EVENTS.split(",")
            },
            headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        self.assertEqual(result, {"status": "created"})

    def test_register_webhook_conflict_fetches_existing(self):
        self.mock_session.put.return_value = MagicMock(
            status_code=HTTPStatus.CONFLICT, text=""
        )
        get_resp = MagicMock(status_code=HTTPStatus.OK)
        get_resp.json.return_value = {"existing": True}
        get_resp.raise_for_status = MagicMock()
        self.mock_session.get.return_value = get_resp

        watcher = GerritSubscriptionService(**self.service_kwargs)
        result = watcher.register_webhook()

        expected_path = (
            f"/a/config/server/webhooks~projects/{TEST_PROJECT}/remotes/{TEST_REMOTE}"
        )
        expected_url = self.fake_client.base_url.rstrip("/") + expected_path

        self.mock_session.get.assert_called_once_with(
            expected_url, headers={"Accept": "application/json"}
        )
        self.assertEqual(result, {"existing": True})

    def test_register_webhook_bad_request_text_fetches_existing(self):
        self.mock_session.put.return_value = MagicMock(
            status_code=HTTPStatus.BAD_REQUEST, text="Already exists"
        )
        get_resp = MagicMock(status_code=HTTPStatus.OK)
        get_resp.json.return_value = {"existing": "conflict"}
        get_resp.raise_for_status = MagicMock()
        self.mock_session.get.return_value = get_resp

        watcher = GerritSubscriptionService(**self.service_kwargs)
        result = watcher.register_webhook()

        self.mock_session.get.assert_called_once()
        self.assertEqual(result, {"existing": "conflict"})

    def test_register_webhook_other_error_raises(self):
        err = HTTPError("Internal Server Error")
        put_resp = MagicMock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        put_resp.raise_for_status.side_effect = err
        self.mock_session.put.return_value = put_resp

        watcher = GerritSubscriptionService(**self.service_kwargs)
        with self.assertRaises(HTTPError):
            watcher.register_webhook()


if __name__ == "__main__":
    main()
