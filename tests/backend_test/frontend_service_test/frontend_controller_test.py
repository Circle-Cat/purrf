from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from flask import Flask
from backend.frontend_service.frontend_controller import (
    frontend_bp,
    FrontendController,
    MicrosoftAccountStatus,
    MicrosoftGroups,
)

MICROSOFT_LDAP_FETCHER_API = "/api/microsoft/{status}/ldaps"
MICROSOFT_CHAT_TOPICS_FETCHER_API = "/api/microsoft/chat/topics"
GOOGLE_CHAT_COUNT_API = "/api/google/chat/count"
JIRA_BRIEF_API = "/api/jira/brief"
GOOGLE_CALENDAR_CALENDARS_API = "/api/google/calendar/calendars"
JIRA_ISSUE_DETAIL_BATCH_API = "/api/jira/detail/batch"
GOOGLE_CALENDAR_EVENTS_API = "/api/google/calendar/events"


class TestFrontendController(TestCase):
    def setUp(self):
        self.ldap_lookup_service = MagicMock()
        self.controller = FrontendController(self.ldap_lookup_service)
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

    async def asyncTearDown(self):
        self.app_context.pop()

    def test_get_ldaps_and_names_success_with_groups(self):
        mock_data = {"active": ["ldap1", "ldap2"]}
        self.ldap_lookup_service.get_ldaps_by_status_and_group.return_value = mock_data

        with self.app.test_request_context(
            "/microsoft/active/ldaps?groups[]=interns&groups[]=employees"
        ):
            response = self.controller.get_ldaps_and_names("active")

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertEqual(response.json["data"], mock_data)

            self.ldap_lookup_service.get_ldaps_by_status_and_group.assert_called_with(
                status=MicrosoftAccountStatus.ACTIVE,
                groups=[MicrosoftGroups.INTERNS, MicrosoftGroups.EMPLOYEES],
            )

    def test_get_ldaps_and_names_success_no_groups(self):
        mock_data = {"all": ["ldap1", "ldap2", "ldap3"]}
        self.ldap_lookup_service.get_ldaps_by_status_and_group.return_value = mock_data

        with self.app.test_request_context("/microsoft/all/ldaps"):
            response = self.controller.get_ldaps_and_names("all")

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertEqual(response.json["data"], mock_data)

            self.ldap_lookup_service.get_ldaps_by_status_and_group.assert_called_with(
                status=MicrosoftAccountStatus.ALL, groups=[]
            )

    def test_get_ldaps_and_names_invalid_status(self):
        with self.app.test_request_context("/microsoft/invalid/ldaps"):
            with self.assertRaises(ValueError):
                self.controller.get_ldaps_and_names("invalid")


class TestAppRoutes(TestCase):
    @classmethod
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(frontend_bp)
        self.client = app.test_client()
        app.testing = True

    @patch("backend.frontend_service.frontend_controller.count_messages_in_date_range")
    def test_count_messages_api_success(self, mock_count):
        mock_count.return_value = {"userA": {"spaceX": 3}}
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&senderLdap=userA&spaceId=spaceX"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"]["userA"]["spaceX"], 3)

    @patch("backend.frontend_service.frontend_controller.count_messages_in_date_range")
    def test_count_messages_api_fallback_sender(self, mock_count):
        mock_count.return_value = {"userB": {"spaceY": 1}}
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&spaceId=spaceY"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("userB", response.json["data"])
        self.assertIn("spaceY", response.json["data"]["userB"])

    @patch("backend.frontend_service.frontend_controller.count_messages_in_date_range")
    def test_count_messages_api_fallback_space_id(self, mock_count):
        mock_count.return_value = {"userC": {"spaceZ": 1}}
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&senderLdap=userC"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("userC", response.json["data"])
        self.assertIn("spaceZ", response.json["data"]["userC"])

    @patch("backend.frontend_service.frontend_controller.count_messages_in_date_range")
    def test_count_messages_api_internal_error(self, mock_count):
        mock_count.side_effect = Exception("Simulated Redis failure")
        with self.assertRaises(Exception):
            self.client.get(
                f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
                f"&senderLdap=userD&spaceId=spaceD"
            )

    @patch("backend.frontend_service.frontend_controller.count_messages_in_date_range")
    def test_count_messages_api_no_params(self, mock_count):
        mock_count.return_value = {"userE": {"spaceE": 5}}
        response = self.client.get(GOOGLE_CHAT_COUNT_API)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"]["userE"]["spaceE"], 5)

    @patch("backend.frontend_service.frontend_controller.count_messages_in_date_range")
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

    @patch("backend.frontend_service.frontend_controller.get_chat_spaces")
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

    @patch("backend.frontend_service.frontend_controller.get_microsoft_chat_topics")
    def test_all_microsoft_chat_topics(self, mock_get):
        mock_get.return_value = {}

        response = self.client.get(MICROSOFT_CHAT_TOPICS_FETCHER_API)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    @patch("backend.frontend_service.frontend_controller.get_issue_ids_in_timerange")
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

    @patch("backend.frontend_service.frontend_controller.get_all_calendars")
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

    @patch(
        "backend.frontend_service.frontend_controller.process_get_issue_detail_batch"
    )
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

    @patch("backend.frontend_service.frontend_controller.get_all_events")
    def test_get_all_events_success(self, mock_get_all_events):
        mock_data = {
            "user1": [
                {
                    "event_id": "event123",
                    "summary": "Team Sync",
                    "calendar_id": "personal",
                    "is_recurring": True,
                    "attendance": [
                        {
                            "join_time": "2025-08-01T10:00:00",
                            "leave_time": "2025-08-01T10:30:00",
                        },
                    ],
                }
            ]
        }
        mock_get_all_events.return_value = mock_data

        params = {
            "calendar_id": "personal",
            "ldaps": "user1",
            "start_date": "2025-07-01T00:00:00",
            "end_date": "2025-08-02T00:00:00",
        }

        response = self.client.get(GOOGLE_CALENDAR_EVENTS_API, query_string=params)
        self.assertEqual(response.status_code, HTTPStatus.OK)

        data = response.get_json()
        self.assertEqual(data["message"], "Calendar events fetched successfully.")
        self.assertEqual(data["data"], mock_data)

    def test_get_all_events_missing_params(self):
        response = self.client.get(
            GOOGLE_CALENDAR_EVENTS_API,
            query_string={
                "ldaps": "user1",
                "start_date": "2025-07-01T00:00:00",
                "end_date": "2025-08-02T00:00:00",
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.get_json()
        self.assertIn("Missing required query parameters", data["message"])


if __name__ == "__main__":
    main()
