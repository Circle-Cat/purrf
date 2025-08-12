import os
import unittest
from unittest.mock import patch, MagicMock
from backend.common.environment_constants import (
    GERRIT_URL,
    GERRIT_USER,
    GERRIT_HTTP_PASS,
)
from backend.common.gerrit_client import GerritClientFactory, GerritClient


class TestGerritClientFactory(unittest.TestCase):
    def test_create_client_singleton(self):
        env = {
            GERRIT_URL: "https://gerrit.test",
            GERRIT_USER: "testuser",
            GERRIT_HTTP_PASS: "testpass",
        }
        with patch.dict(os.environ, env, clear=True):
            factory1 = GerritClientFactory()
            client1 = factory1.create_gerrit_client()
            client2 = factory1.create_gerrit_client()
            self.assertIs(client1, client2)
            self.assertIsInstance(client1, GerritClient)
            self.assertEqual(client1.session.auth, ("testuser", "testpass"))


class TestQueryChanges(unittest.TestCase):
    def setUp(self):
        self.client = GerritClient(
            base_url="https://gerrit.test", username="user", http_password="pass"
        )
        self.patcher = patch.object(self.client, "session", autospec=True)
        self.mock_session = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_query_changes_with_parameters(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = '[{"id": 1}]'
        self.mock_session.get.return_value = mock_resp

        result = self.client.query_changes(
            queries=["status:open", "project:foo"],
            limit=10,
            start=5,
            no_limit=False,
            options=["CURRENT_REVISION"],
            allow_incomplete=True,
        )

        self.assertEqual(result, [{"id": 1}])

        expected_url = "https://gerrit.test/changes/"
        self.mock_session.get.assert_called_once()
        args, kwargs = self.mock_session.get.call_args
        self.assertEqual(args[0], expected_url)
        params = kwargs.get("params")
        expected_params = [
            ("q", "status:open"),
            ("q", "project:foo"),
            ("n", "10"),
            ("S", "5"),
            ("allow-incomplete-results", "true"),
            ("o", "CURRENT_REVISION"),
        ]
        for ep in expected_params:
            self.assertIn(ep, params)

    def test_query_changes_no_limit(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = '[{"id": 2}]'
        self.mock_session.get.return_value = mock_resp

        result = self.client.query_changes(
            queries="status:merged",
            limit=50,
            no_limit=True,
        )
        self.assertEqual(result, [{"id": 2}])

        kwargs = self.mock_session.get.call_args[1]
        params = kwargs.get("params")
        self.assertIn(("no-limit", "true"), params)
        self.assertNotIn(("n", "50"), params)


if __name__ == "__main__":
    unittest.main()
