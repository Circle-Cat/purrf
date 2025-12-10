from unittest import TestCase, main
from unittest.mock import patch
from http import HTTPStatus
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.common.fast_api_error_handler import register_exception_handlers

# Constant definitions
VALUE_ERROR_MSG = "Invalid input"
RUNTIME_ERROR_MSG = "Service unavailable"
UNEXPECTED_ERROR_MSG = "Unexpected fatal error"
GENERIC_SERVER_ERROR_MSG = "Internal Server Error. Please contact support."
ERROR_KEY = "message"


class TestFastAPIExceptionHandler(TestCase):
    def setUp(self):
        # Create a FastAPI instance
        self.app = FastAPI()

        # Register global exception handlers
        register_exception_handlers(self.app)

        # Initialize TestClient (ignore server exceptions so we can inspect API responses)
        self.client = TestClient(self.app, raise_server_exceptions=False)

        # Patch the logger used in the exception handler
        self.logger_patcher = patch("backend.common.fast_api_error_handler.logger")
        self.mock_logger = self.logger_patcher.start()

    def tearDown(self):
        self.logger_patcher.stop()

    def test_handle_value_error(self):
        """400 Client Error (ValueError): the raw error message should be shown and logged as warning."""
        route = "/api/test/value_error"

        @self.app.get(route)
        def trigger_error():
            raise ValueError(VALUE_ERROR_MSG)

        response = self.client.get(route)

        # Status should be 400 Bad Request
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

        # Response should contain the original error message
        self.assertEqual(response.json().get(ERROR_KEY), VALUE_ERROR_MSG)

        # Logger should use warning instead of error
        self.mock_logger.warning.assert_called_once()
        self.mock_logger.error.assert_not_called()

        # Platform extraction check: route is /api/test/value_error -> platform = "test"
        args, _ = self.mock_logger.warning.call_args
        self.assertIn("test", args)

    def test_handle_request_validation_error(self):
        """400 Validation Error: should return a formatted validation message."""
        route = "/api/test/validation"

        class Item(BaseModel):
            price: int

        @self.app.post(route)
        def trigger_validation(item: Item):
            return item

        # Trigger validation error (string instead of int)
        response = self.client.post(route, json={"price": "not_an_int"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

        data = response.json()

        # Should return formatted validation message
        self.assertTrue(data.get(ERROR_KEY).startswith("Validation Error"))
        self.assertIn("price", data.get(ERROR_KEY))

        # Should log as warning
        self.mock_logger.warning.assert_called_once()

    def test_handle_runtime_error(self):
        """503 Service Unavailable: error message should be masked; log should be error level."""
        route = "/api/chat/pull"

        @self.app.get(route)
        def trigger_error():
            raise RuntimeError(RUNTIME_ERROR_MSG)

        response = self.client.get(route)

        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)

        # Server errors must not expose real details to the client
        self.assertEqual(response.json().get(ERROR_KEY), GENERIC_SERVER_ERROR_MSG)

        # Logger must use error level
        self.mock_logger.error.assert_called_once()
        args, kwargs = self.mock_logger.error.call_args

        # Log should include real platform and real error message
        self.assertIn("chat", args)
        self.assertIn(RUNTIME_ERROR_MSG, args)

        # Stack trace must be included for server errors
        self.assertTrue(kwargs.get("exc_info"))

    def test_handle_unexpected_error(self):
        """500 Internal Server Error: message should be masked; log should contain real details."""
        route = "/api/jira/search"

        @self.app.get(route)
        def trigger_error():
            raise Exception(UNEXPECTED_ERROR_MSG)

        response = self.client.get(route)

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

        # Client should see masked error
        self.assertEqual(response.json().get(ERROR_KEY), GENERIC_SERVER_ERROR_MSG)

        # Log real details
        self.mock_logger.error.assert_called_once()
        args, _ = self.mock_logger.error.call_args

        self.assertIn("jira", args)
        self.assertIn(UNEXPECTED_ERROR_MSG, args)

    def test_platform_extraction_root(self):
        """If the path has no second segment, platform should default to 'unknown'."""
        route = "/unknown_route"

        @self.app.get(route)
        def trigger_error():
            raise ValueError("Test")

        self.client.get(route)

        args, _ = self.mock_logger.warning.call_args

        # Platform should be "unknown"
        self.assertIn("unknown", args)


if __name__ == "__main__":
    main()
