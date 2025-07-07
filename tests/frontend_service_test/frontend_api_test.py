from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import patch
from flask import Flask
from src.frontend_service.frontend_api import frontend_bp
from src.common.constants import MicrosoftAccountStatus

MICROSOFT_LDAP_FETCHER_API = "/api/microsoft/{status}/ldaps"
GOOGLE_CHAT_COUNT_API = "/api/google/chat/count"


class TestAppRoutes(TestCase):
    @classmethod
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(frontend_bp)
        self.client = app.test_client()
        app.testing = True

    @patch("src.frontend_service.frontend_api.get_all_ldaps_and_displaynames")
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
        with self.assertRaises(ValueError) as context:
            self.client.get(MICROSOFT_LDAP_FETCHER_API.format(status="invalid_status"))

    @patch("src.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_success(self, mock_count):
        mock_count.return_value = {"userA": {"spaceX": 3}}
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&senderLdap=userA&spaceId=spaceX"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"]["userA"]["spaceX"], 3)

    @patch("src.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_fallback_sender(self, mock_count):
        mock_count.return_value = {"userB": {"spaceY": 1}}
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&spaceId=spaceY"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("userB", response.json["data"])
        self.assertIn("spaceY", response.json["data"]["userB"])

    @patch("src.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_fallback_space_id(self, mock_count):
        mock_count.return_value = {"userC": {"spaceZ": 1}}
        response = self.client.get(
            f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
            f"&senderLdap=userC"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("userC", response.json["data"])
        self.assertIn("spaceZ", response.json["data"]["userC"])

    @patch("src.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_internal_error(self, mock_count):
        mock_count.side_effect = Exception("Simulated Redis failure")
        with self.assertRaises(Exception):
            self.client.get(
                f"{GOOGLE_CHAT_COUNT_API}?startDate=2024-12-01&endDate=2024-12-15"
                f"&senderLdap=userD&spaceId=spaceD"
            )

    @patch("src.frontend_service.frontend_api.count_messages_in_date_range")
    def test_count_messages_api_no_params(self, mock_count):
        mock_count.return_value = {"userE": {"spaceE": 5}}
        response = self.client.get(GOOGLE_CHAT_COUNT_API)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"]["userE"]["spaceE"], 5)

    @patch("src.frontend_service.frontend_api.count_messages_in_date_range")
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

    @patch("src.frontend_service.frontend_api.get_chat_spaces")
    def test_get_chat_spaces_route_success(self, mock_get_chat_spaces):
        mock_spaces = [{"name": "spaces/abc123", "spaceType": "SPACE"}]
        mock_get_chat_spaces.return_value = mock_spaces

        response = self.client.get("/api/google/chat/spaces?space_type=SPACE&page_size=50")
        self.assertEqual(response.status_code, HTTPStatus.OK)

        json_data = response.get_json()
        self.assertEqual(json_data["message"], "Retrieve chat spaces successfully.")
        self.assertEqual(json_data["data"], mock_spaces)

        mock_get_chat_spaces.assert_called_once_with("SPACE", 50)

if __name__ == "__main__":
    main()
