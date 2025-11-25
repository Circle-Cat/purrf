import os
import json
from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from backend.common.gerrit_client import GerritClient


class TestQueryChanges(TestCase):
    def setUp(self):
        env = {
            "GERRIT_URL": "https://gerrit.test",
            "GERRIT_USER": "user",
            "GERRIT_HTTP_PASS": "pass",
        }
        self.env_patcher = patch.dict(os.environ, env)
        self.env_patcher.start()

        self.client = GerritClient()

        self.patcher = patch.object(self.client, "session", autospec=True)
        self.mock_session = self.patcher.start()

        self.base_url = os.environ.get("GERRIT_URL")

    def tearDown(self):
        self.patcher.stop()
        self.env_patcher.stop()

    def test_init_raises_value_error_if_url_missing(self):
        with patch.dict(os.environ, {"GERRIT_URL": ""}):
            with self.assertRaises(ValueError):
                GerritClient()

    def test_init_raises_value_error_if_user_missing(self):
        with patch.dict(os.environ, {"GERRIT_USER": ""}):
            with self.assertRaises(ValueError):
                GerritClient()

    def test_init_raises_value_error_if_password_missing(self):
        with patch.dict(os.environ, {"GERRIT_HTTP_PASS": ""}):
            with self.assertRaises(ValueError):
                GerritClient()

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

        expected_url = f"{self.base_url}/changes/"
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

    def test_get_projects_success(self):
        """Tests successful retrieval and parsing of projects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_projects_data = {
            "project-one": {"id": "project-one", "state": "ACTIVE"},
            "project-two": {"id": "project-two", "state": "READ_ONLY"},
        }
        mock_response.text = ")]}'\n" + json.dumps(mock_projects_data)
        mock_response.raise_for_status.return_value = None
        self.mock_session.get.return_value = mock_response

        projects = self.client.get_projects()

        self.mock_session.get.assert_called_once_with(f"{self.base_url}/projects/")
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(projects, mock_projects_data)

    def test_get_projects_json_decode_error(self):
        """Tests handling of invalid JSON in the response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ")]}'\n" + "this is not valid json"
        mock_response.raise_for_status.return_value = None
        self.mock_session.get.return_value = mock_response

        with self.assertRaises(json.JSONDecodeError):
            self.client.get_projects()

    def test_get_change_by_change_id_success(self):
        """Tests successful retrieval and parsing of a change by change_id."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_change_data = {
            "id": "12345",
            "project": "project-one",
            "insertions": 10,
            "deletions": 2,
            "status": "MERGED",
        }
        # Gerrit prepends ")]}'\n" to responses
        mock_response.text = ")]}'\n" + json.dumps(mock_change_data)
        mock_response.raise_for_status.return_value = None
        self.mock_session.get.return_value = mock_response

        change_info = self.client.get_change_by_change_id("12345")

        self.mock_session.get.assert_called_once_with(f"{self.base_url}/changes/12345")
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(change_info, mock_change_data)

    def test_get_change_by_change_id_none(self):
        """Tests that passing None as change_id raises ValueError."""
        with self.assertRaises(ValueError):
            self.client.get_change_by_change_id(None)

    def test_get_change_by_change_id_json_decode_error(self):
        """Tests handling of invalid JSON in the response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ")]}'\n" + "invalid json"
        mock_response.raise_for_status.return_value = None
        self.mock_session.get.return_value = mock_response

        with self.assertRaises(json.JSONDecodeError):
            self.client.get_change_by_change_id("12345")


if __name__ == "__main__":
    main()
