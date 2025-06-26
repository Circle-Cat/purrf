from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import patch
from flask import Flask, jsonify
from src.historical_data.historical_api import history_bp
from src.common.constants import MicrosoftAccountStatus


MICROSOFT_LDAP_FETCHER_API = "/api/microsoft/backfill/ldaps"
MICROSOFT_CHAT_FETCHER_API = "/microsoft/fetch/history/messages/{chat_id}"
TEST_CHAT_ID = "chat131"


class TestAppRoutes(TestCase):
    @classmethod
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(history_bp)
        self.client = app.test_client()
        app.testing = True

    @patch("src.historical_data.historical_api.sync_microsoft_members_to_redis")
    def test_backfill_microsoft_ldaps(self, mock_sync_microsoft_members_to_redis):
        mock_result = {
            MicrosoftAccountStatus.ACTIVE.value: 3,
            MicrosoftAccountStatus.TERMINATED.value: 2,
        }
        mock_sync_microsoft_members_to_redis.return_value = mock_result

        response = self.client.post(MICROSOFT_LDAP_FETCHER_API)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)

        mock_sync_microsoft_members_to_redis.assert_called_once_with()

    @patch("src.historical_data.historical_api.sync_microsoft_chat_messages_by_chat_id")
    def backfill_microsoft_chat_messages(
        self, mock_sync_microsoft_chat_messages_by_chat_id
    ):
        mock_result = {"total_processed": 5, "total_skipped": 0}
        mock_sync_microsoft_members_to_redis.return_value = mock_result

        response = self.client.post(
            MICROSOFT_CHAT_FETCHER_API.format(chat_id=TEST_CHAT_ID)
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)

        mock_sync_microsoft_chat_messages_by_chat_id.assert_called_once_with()


if __name__ == "__main__":
    main()
