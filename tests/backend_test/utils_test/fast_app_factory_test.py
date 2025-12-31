import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from backend.utils.fast_app_factory import FastAppFactory


class TestFastAppFactory(unittest.TestCase):
    def setUp(self):
        self.mock_controller = MagicMock()
        self.mock_controller.router = MagicMock()
        self.mock_profile_controller = MagicMock()
        self.mock_profile_controller.router = MagicMock()
        self.mock_service = MagicMock()

        self.factory = FastAppFactory(
            authentication_controller=self.mock_controller,
            authentication_service=self.mock_service,
            notification_controller=self.mock_controller,
            historical_controller=self.mock_controller,
            consumer_controller=self.mock_controller,
            frontend_controller=self.mock_controller,
            profile_controller=self.mock_profile_controller,
            mentorship_controller=self.mock_controller,
        )

    def test_factory_initialization(self):
        """Test whether the factory class can be instantiated."""
        self.assertIsInstance(self.factory, FastAppFactory)
        self.assertEqual(self.factory.authentication_controller, self.mock_controller)
        self.assertEqual(self.factory.authentication_service, self.mock_service)
        self.assertEqual(self.factory.notification_controller, self.mock_controller)
        self.assertEqual(self.factory.historical_controller, self.mock_controller)
        self.assertEqual(self.factory.consumer_controller, self.mock_controller)
        self.assertEqual(self.factory.frontend_controller, self.mock_controller)
        self.assertEqual(self.factory.mentorship_controller, self.mock_controller)

    def test_create_app_returns_fastapi_instance(self):
        """Test that create_app returns a FastAPI application instance."""
        app = self.factory.create_app()
        self.assertIsInstance(app, FastAPI)

    @patch("backend.utils.fast_app_factory.register_exception_handlers")
    def test_exception_handler_registration_called(self, mock_register):
        """
        Test that the exception handler registration function is called
        when the application is created.
        """
        self.factory.create_app()

        # register_exception_handlers should be called exactly once
        mock_register.assert_called_once()

        # It should receive a FastAPI instance
        call_args = mock_register.call_args
        self.assertIsInstance(call_args[0][0], FastAPI)

    def test_auth_middleware_added(self):
        """Test that AuthMiddleware is added to the FastAPI app."""
        app = self.factory.create_app()
        # FastAPI middleware is stored in app.user_middleware
        middleware_classes = [m.cls for m in app.user_middleware]
        from backend.utils.auth_middleware import AuthMiddleware

        self.assertIn(AuthMiddleware, middleware_classes)


if __name__ == "__main__":
    unittest.main()
