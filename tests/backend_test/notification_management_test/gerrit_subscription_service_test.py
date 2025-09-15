import os
from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import MagicMock, patch
from requests.exceptions import HTTPError

from backend.notification_management.gerrit_subscription_service import (
    GerritSubscriptionService,
)
from backend.common.environment_constants import (
    GERRIT_WEBHOOK_TARGET_URL,
    GERRIT_WEBHOOK_SECRET,
    GERRIT_WEBHOOK_PROJECT,
    GERRIT_WEBHOOK_REMOTE_NAME,
    GERRIT_WEBHOOK_EVENTS,
)

TEST_PROJECT = "test-project"
TEST_REMOTE = "test-remote"
TEST_TARGET_URL = "http://example.com/webhook"
TEST_SECRET = "supersecret"
TEST_EVENTS = "one,two,three"


class TestGerritSubscriptionService(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_session = MagicMock()
        self.fake_client = MagicMock(
            base_url="http://gerrit.example.com/", session=self.mock_session
        )

        env = {
            GERRIT_WEBHOOK_TARGET_URL: TEST_TARGET_URL,
            GERRIT_WEBHOOK_SECRET: TEST_SECRET,
            GERRIT_WEBHOOK_EVENTS: TEST_EVENTS,
            GERRIT_WEBHOOK_PROJECT: TEST_PROJECT,
            GERRIT_WEBHOOK_REMOTE_NAME: TEST_REMOTE,
        }
        self.env_patcher = patch.dict(os.environ, env, clear=True)
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

    def test_init_missing_target_url_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                GerritSubscriptionService(self.mock_logger, self.fake_client)

    def test_register_webhook_success_and_secret_and_events(self):
        put_resp = MagicMock(status_code=HTTPStatus.CREATED)
        put_resp.json.return_value = {"status": "created"}
        self.mock_session.put.return_value = put_resp

        watcher = GerritSubscriptionService(
            logger=self.mock_logger, gerrit_client=self.fake_client
        )
        result = watcher.register_webhook()

        expected_path = (
            f"/a/config/server/webhooks~projects/{TEST_PROJECT}/remotes/{TEST_REMOTE}"
        )
        expected_url = self.fake_client.base_url.rstrip("/") + expected_path
        self.mock_session.put.assert_called_once_with(
            expected_url,
            json={
                "url": TEST_TARGET_URL,
                "events": TEST_EVENTS.split(","),
                "secret": TEST_SECRET,
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

        watcher = GerritSubscriptionService(
            logger=self.mock_logger, gerrit_client=self.fake_client
        )
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

        watcher = GerritSubscriptionService(
            logger=self.mock_logger, gerrit_client=self.fake_client
        )
        result = watcher.register_webhook()

        self.mock_session.get.assert_called_once()
        self.assertEqual(result, {"existing": "conflict"})

    def test_register_webhook_other_error_raises(self):
        err = HTTPError("Internal Server Error")
        put_resp = MagicMock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        put_resp.raise_for_status.side_effect = err
        self.mock_session.put.return_value = put_resp

        watcher = GerritSubscriptionService(
            logger=self.mock_logger, gerrit_client=self.fake_client
        )
        with self.assertRaises(HTTPError):
            watcher.register_webhook()


if __name__ == "__main__":
    main()
