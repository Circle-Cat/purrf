import unittest
from unittest.mock import patch
from fastapi import FastAPI
from backend.utils.fast_app_factory import FastAppFactory


class TestFastAppFactory(unittest.TestCase):
    def setUp(self):
        self.factory = FastAppFactory()

    def test_factory_initialization(self):
        """Test whether the factory class can be instantiated."""
        self.assertIsInstance(self.factory, FastAppFactory)

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

        # Additional assertion: the function should receive a FastAPI instance
        # call_args[0] contains the positional arguments from the first call
        call_args = mock_register.call_args
        self.assertIsInstance(call_args[0][0], FastAPI)


if __name__ == "__main__":
    unittest.main()
