from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import patch
from flask import Flask
from backend.frontend_service.frontend_api import frontend_bp
from backend.common.constants import MicrosoftAccountStatus

MICROSOFT_LDAP_FETCHER_API = "/api/microsoft/{status}/ldaps"
MICROSOFT_CHAT_TOPICS_FETCHER_API = "/api/microsoft/chat/topics"
GOOGLE_CHAT_COUNT_API = "/api/google/chat/count"
JIRA_BRIEF_API = "/api/jira/brief"
GOOGLE_CALENDAR_CALENDARS_API = "/api/google/calendar/calendars"
JIRA_ISSUE_DETAIL_BATCH_API = "/api/jira/detail/batch"


class TestAppRoutes(TestCase):
    @classmethod
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(frontend_bp)
        self.client = app.test_client()
        app.testing = True

    @patch("backend.frontend_service.frontend_api.get_all_ldaps_and_displaynames")
    def test_get_microsoft_ldaps_success(self, mock_get_all_ldaps):
        mock_result = {"user1": "ldap1", "user2": "ldap2"}
        mock_get_all_ldaps.return_value = mock_result
        response = self.client.get(
            MICROSOFT_LDAP_FETCHER_API.format(
                status=MicrosoftAccountStatus.ACTIVE.value
            )
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)
        mock_get_all_ldaps.assert_called_once_with(MicrosoftAccountStatus.ACTIVE)

    def test_get_microsoft_ldaps_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            self.client.get(MICROSOFT_LDAP_FETCHER_API.format(status="invalid_status"))

    @patch("backend.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_success(self, mock_count):
        mock_count.return_value = {"userA": {"spaceX": 3}}
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&senderLdap=userA&spaceId=spaceX"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"]["userA"]["spaceX"], 3)

    @patch("backend.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_fallback_sender(self, mock_count):
        mock_count.return_value = {"userB": {"spaceY": 1}}
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&spaceId=spaceY"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("userB", response.json["data"])
        self.assertIn("spaceY", response.json["data"]["userB"])

    @patch("backend.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_fallback_space_id(self, mock_count):
        mock_count.return_value = {"userC": {"spaceZ": 1}}
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&senderLdap=userC"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("userC", response.json["data"])
        self.assertIn("spaceZ", response.json["data"]["userC"])

    @patch("backend.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_internal_error(self, mock_count):
        mock_count.side_effect = Exception("Simulated Redis failure")
        with self.assertRaises(Exception):
            self.client.get(
                f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
                f"&senderLdap=userD&spaceId=spaceD"
            )

    @patch("backend.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_no_params(self, mock_count):
        mock_count.return_value = {"userE": {"spaceE": 5}}
        response = self.client.get(GOOGLE_CHAT_COUNT_API)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"]["userE"]["spaceE"], 5)

    @patch("backend.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_multiple_sender_and_space(self, mock_count):
        mock_count.return_value = {
            "alice": {"space1": 3, "space2": 1},
            "bob": {"space1": 0, "space2": 2},
        }
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&spaceId=space1&spaceId=space2"
            f"&senderLdap=alice&senderLdap=bob"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"]["alice"]["space1"], 3)
        self.assertEqual(response.json["data"]["alice"]["space2"], 1)
        self.assertEqual(response.json["data"]["bob"]["space1"], 0)
        self.assertEqual(response.json["data"]["bob"]["space2"], 2)

    @patch("backend.frontend_service.frontend_api.get_chat_spaces")
    def test_get_chat_spaces_route_success(self, mock_get_chat_spaces):
        mock_spaces = [{"name": "spaces/abc123", "spaceType": "SPACE"}]
        mock_get_chat_spaces.return_value = mock_spaces

        response = self.client.get(
            "/api/google/chat/spaces?space_type=SPACE&page_size=50"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

        json_data = response.get_json()
        self.assertEqual(json_data["message"], "Retrieve chat spaces successfully.")
        self.assertEqual(json_data["data"], mock_spaces)

        mock_get_chat_spaces.assert_called_once_with("SPACE", 50)

    @patch("backend.frontend_service.frontend_api.get_microsoft_chat_topics")
    def test_all_microsoft_chat_topics(self, mock_get):
        mock_get.return_value = {}

        response = self.client.get(MICROSOFT_CHAT_TOPICS_FETCHER_API)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    @patch("backend.frontend_service.frontend_api.get_issue_ids_in_timerange")
    def test_jira_brief_success(self, mock_process):
        mock_result = {"todo": {"alice": {"projectA": [101, 102]}}}
        mock_process.return_value = mock_result
        response = self.client.post(
            JIRA_BRIEF_API,
            json={"status": "todo", "ldaps": ["alice"], "project_ids": ["projectA"]},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)
        mock_process.assert_called_once_with(
            status="todo",
            ldaps=["alice"],
            project_ids=["projectA"],
            start_date=None,
            end_date=None,
        )

    @patch("backend.frontend_service.frontend_api.get_all_calendars")
    def test_get_google_calendar_calendars_success(self, mock_get_all_calendars):
        mock_result = [
            {"id": "calendar_id_1", "name": "Work"},
            {"id": "calendar_id_2", "name": "Personal"},
        ]
        mock_get_all_calendars.return_value = mock_result

        response = self.client.get(f"{GOOGLE_CALENDAR_CALENDARS_API}")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.get_json()
        self.assertEqual(data["message"], "Calendar list fetched successfully.")
        self.assertEqual(len(data["data"]), 2)
        self.assertEqual(data["data"][0]["id"], "calendar_id_1")

    @patch("backend.frontend_service.frontend_api.process_get_issue_detail_batch")
    def test_get_issue_detail_batch_success(self, mock_process):
        mock_result = {
            "abc123": {
                "ldap": "test_ldap",
                "finish_date": 20991231,
                "issue_key": "TEST-999",
                "story_point": 42,
                "project_id": 112233,
                "project_name": "test_proj_name",
                "issue_status": "testing",
                "issue_title": "This is an issue for unit test",
            }
        }
        mock_process.return_value = mock_result
        response = self.client.post(
            "/api/jira/detail/batch", json={"issue_ids": ["abc123"]}
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)
        mock_process.assert_called_once_with(["abc123"])


if __name__ == "__main__":
    main()
