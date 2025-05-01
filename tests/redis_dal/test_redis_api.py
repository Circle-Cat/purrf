import unittest
from unittest.mock import patch
from redis_dal.redis_api import redis_api
from flask import Flask
from tools.global_handle_exception.exception_handler import register_error_handlers
from http import HTTPStatus


class TestRedisApi(unittest.TestCase):
    BASE_URL = "/api/chat/count"

    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(redis_api, url_prefix="/api")
        register_error_handlers(self.app)
        self.client = self.app.test_client()

    @patch("redis_dal.redis_api.count_messages_in_date_range")
    def test_count_messages_api_success(self, mock_count):
        mock_count.return_value = {"userA": {"spaceX": 3}}
        response = self.client.get(
            f"{self.BASE_URL}?startDate=2024-12-01&endDate=2024-12-15&senderLdap=userA&spaceId=spaceX"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["userA"]["spaceX"], 3)

    @patch("redis_dal.redis_api.count_messages_in_date_range")
    def test_count_messages_api_fallback_sender(self, mock_count):
        mock_count.return_value = {"userB": {"spaceY": 1}}
        response = self.client.get(
            f"{self.BASE_URL}?startDate=2024-12-01&endDate=2024-12-15&spaceId=spaceY"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("userB", response.json)
        self.assertIn("spaceY", response.json["userB"])

    @patch("redis_dal.redis_api.count_messages_in_date_range")
    def test_count_messages_api_fallback_space_id(self, mock_count):
        mock_count.return_value = {"userC": {"spaceZ": 1}}
        response = self.client.get(
            f"{self.BASE_URL}?startDate=2024-12-01&endDate=2024-12-15&senderLdap=userC"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("userC", response.json)
        self.assertIn("spaceZ", response.json["userC"])

    @patch("redis_dal.redis_api.count_messages_in_date_range")
    def test_count_messages_api_internal_error(self, mock_count):
        mock_count.side_effect = Exception("Simulated Redis failure")
        response = self.client.get(
            f"{self.BASE_URL}?startDate=2024-12-01&endDate=2024-12-15&senderLdap=userD&spaceId=spaceD"
        )
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)


if __name__ == "__main__":
    unittest.main()
