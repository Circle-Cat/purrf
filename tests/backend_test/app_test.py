from unittest import TestCase, main
from unittest.mock import MagicMock
from http import HTTPStatus
from backend.app import create_app

HEALTH_API = "/health"


class TestAppRoutes(TestCase):
    def setUp(self):
        self.app = create_app(
            notification_controller=MagicMock(),
            consumer_controller=MagicMock(),
            historical_controller=MagicMock(),
            frontend_controller=MagicMock(),
        )
        self.app.testing = True
        self.client = self.app.test_client()

    def test_health_check(self):
        response = self.client.get(HEALTH_API)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.get_json()
        self.assertEqual(data["message"], "Success.")


if __name__ == "__main__":
    main()
