from unittest import TestCase, main
from http import HTTPStatus
from flask import Flask, json
from backend.common.error_handler import handle_exception, register_error_handlers

VALUE_ERROR = "Invalid input"
RUNTIME_ERROR = "Service unavailable"
EXCEPTION = "Unexpected error"
TEST_ROUTE = "/test_error"
ERROR_MESSAGE = "message"


class TestExceptionHandler(TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        register_error_handlers(self.app)
        self.app.testing = True

    def test_handle_value_error(self):
        e = ValueError(VALUE_ERROR)
        with self.app.app_context():
            response = handle_exception(e)
            self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
            data = response.get_json()
            self.assertEqual(data.get(ERROR_MESSAGE), VALUE_ERROR)

    def test_handle_runtime_error(self):
        e = RuntimeError(RUNTIME_ERROR)
        with self.app.app_context():
            response = handle_exception(e)
            self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            data = response.get_json()
            self.assertEqual(data.get(ERROR_MESSAGE), RUNTIME_ERROR)

    def test_handle_unexpected_error(self):
        e = Exception(EXCEPTION)
        with self.app.app_context():
            response = handle_exception(e)
            self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            data = response.get_json()
            self.assertEqual(data.get(ERROR_MESSAGE), EXCEPTION)

    def test_register_error_handlers(self):
        with self.app.test_client() as client:

            @self.app.route(TEST_ROUTE)
            def test_error():
                raise ValueError(VALUE_ERROR)

            response = client.get(TEST_ROUTE)
            self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
            data = response.get_json()
            self.assertEqual(data.get(ERROR_MESSAGE), VALUE_ERROR)


if __name__ == "__main__":
    main()
