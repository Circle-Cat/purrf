from unittest import TestCase, main
from unittest.mock import MagicMock
from http import HTTPStatus
from backend.app import App

HEALTH_API = "/health"


class TestApp(TestCase):
    def setUp(self):
        self.mock_consumer_controller = MagicMock()
        self.mock_historical_controller = MagicMock()
        self.mock_frontend_controller = MagicMock()

        self.app_factory = App(
            consumer_controller=self.mock_consumer_controller,
            historical_controller=self.mock_historical_controller,
            frontend_controller=self.mock_frontend_controller,
        )
        self.app = self.app_factory.create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def test_create_app_registers_routes(self):
        """
        Verify that all controller's register_routes methods are called.
        """
        self.mock_consumer_controller.register_routes.assert_called_once()
        self.mock_historical_controller.register_routes.assert_called_once()
        self.mock_frontend_controller.register_routes.assert_called_once()

    def test_health_check(self):
        """
        Test the /health endpoint to ensure it returns a successful response.
        """
        response = self.client.get(HEALTH_API)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.get_json()
        self.assertEqual(data["message"], "Success.")


if __name__ == "__main__":
    main()
