import unittest
from flask import Flask
import http.client
import logging
from io import StringIO
from tools.log.logger import setup_logger
from tools.global_handle_exception.exception_handler import (
    handle_exception,
    register_error_handlers,
)
from tools.global_handle_exception.constants import (
    VALUE_ERROR_LOG_MSG,
    RUNTIME_ERROR_LOG_MSG,
    UNEXPECTED_ERROR_LOG_MSG,
    ERROR_MESSAGE,
)

VALUE_ERROR = "Invalid input"
RUNTIME_ERROR = "Service unavailable"
EXCEPTION = "Unexpected error"
TEST_ROUTE = "/test_error"


class TestExceptionHandler(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.log_capture_string = StringIO()
        ch = logging.StreamHandler(self.log_capture_string)
        setup_logger()
        root_logger = logging.getLogger()
        ch.setFormatter(root_logger.handlers[0].formatter)
        logging.getLogger().addHandler(ch)

    def tearDown(self):
        logging.getLogger().handlers = []

    def test_handle_value_error(self):
        e = ValueError(VALUE_ERROR)
        with self.app.app_context():
            response, status_code = handle_exception(e)
            self.assertEqual(status_code, http.client.BAD_REQUEST)
            self.assertEqual(response.get_json(), {ERROR_MESSAGE: VALUE_ERROR})
            self.assertIn(
                VALUE_ERROR_LOG_MSG.format(error_msg=VALUE_ERROR),
                self.log_capture_string.getvalue(),
            )

    def test_handle_runtime_error(self):
        e = RuntimeError(RUNTIME_ERROR)
        with self.app.app_context():
            response, status_code = handle_exception(e)
            self.assertEqual(status_code, http.client.SERVICE_UNAVAILABLE)
            self.assertEqual(response.get_json(), {ERROR_MESSAGE: RUNTIME_ERROR})
            self.assertIn(
                RUNTIME_ERROR_LOG_MSG.format(error_msg=RUNTIME_ERROR),
                self.log_capture_string.getvalue(),
            )

    def test_handle_unexpected_error(self):
        e = Exception(EXCEPTION)
        with self.app.app_context():
            response, status_code = handle_exception(e)
            self.assertEqual(status_code, http.client.INTERNAL_SERVER_ERROR)
            self.assertEqual(response.get_json(), {ERROR_MESSAGE: EXCEPTION})
            self.assertIn(
                UNEXPECTED_ERROR_LOG_MSG.format(error_msg=EXCEPTION),
                self.log_capture_string.getvalue(),
            )

    def test_register_error_handlers(self):
        register_error_handlers(self.app)
        with self.app.test_client() as client:
            with self.app.app_context():

                @self.app.route(TEST_ROUTE)
                def test_error():
                    raise ValueError(VALUE_ERROR)

                response = client.get(TEST_ROUTE)
                self.assertEqual(response.status_code, http.client.BAD_REQUEST)
                self.assertEqual(response.get_json(), {ERROR_MESSAGE: VALUE_ERROR})


if __name__ == "__main__":
    unittest.main()
