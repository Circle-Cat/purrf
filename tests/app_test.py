"""Test for purrf"""

from http import HTTPStatus
from unittest import TestCase, main
from src.app import app

HEALTH_API = "/health"


class TestAppRoutes(TestCase):
    @classmethod
    def setUp(self):
        self.client = app.test_client()
        app.testing = True

    def test_health_check(self):
        """Testing health check endpoint"""
        response = self.client.get(HEALTH_API)
        self.assertEqual(response.status_code, HTTPStatus.OK)

        data = response.get_json()
        self.assertEqual(data.get("message"), "Success.")
        self.assertEqual(data.get("data"), {})


if __name__ == "__main__":
    main()
