import json
import logging
import os
import unittest
from io import StringIO
from unittest.mock import patch

from backend.common.environment_constants import LOG_LEVEL
from backend.common.logger import get_logger
import backend.common.logger as logger_module


class TestLogger(unittest.TestCase):
    def setUp(self):
        logging.getLogger().handlers = []
        logging.getLogger().setLevel(logging.NOTSET)
        logger_module._logger_initialized = False

    def tearDown(self):
        logging.getLogger().handlers = []

    def test_default_log_level(self):
        get_logger()
        self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.INFO)

    def test_custom_log_level(self):
        with patch.dict(os.environ, {LOG_LEVEL: "DEBUG"}):
            get_logger()
            self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.DEBUG)

    def test_invalid_log_level(self):
        with patch.dict(os.environ, {LOG_LEVEL: "INVALID"}):
            get_logger()
            self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.INFO)

    def test_json_log_format(self):
        with patch.dict(os.environ, {LOG_LEVEL: "INFO"}):
            get_logger()
            log_capture = StringIO()
            root_logger = logging.getLogger()
            root_logger.handlers[0].stream = log_capture

            logging.info("Test message")
            log_output = log_capture.getvalue().strip()
            log_entry = json.loads(log_output)

            self.assertEqual(log_entry["severity"], "INFO")
            self.assertEqual(log_entry["message"], "Test message")
            self.assertIn("timestamp", log_entry)
            self.assertIn("+00:00", log_entry["timestamp"])
            self.assertIn("name", log_entry)
            self.assertNotIn("levelname", log_entry)

    def test_json_log_with_exception(self):
        with patch.dict(os.environ, {LOG_LEVEL: "INFO"}):
            get_logger()
            log_capture = StringIO()
            root_logger = logging.getLogger()
            root_logger.handlers[0].stream = log_capture

            try:
                raise ValueError("test error")
            except ValueError:
                logging.error("Something failed", exc_info=True)

            log_output = log_capture.getvalue().strip()
            log_entry = json.loads(log_output)

            self.assertEqual(log_entry["severity"], "ERROR")
            self.assertIn("stack_trace", log_entry)
            self.assertIn("ValueError: test error", log_entry["stack_trace"])

    def test_setup_logger_called_once(self):
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = mock_get_logger.return_value
            mock_root.handlers = []
            get_logger()
            get_logger()
            get_logger()

            # _setup_logger only configures root logger once due to _logger_initialized flag
            self.assertTrue(logger_module._logger_initialized)


if __name__ == "__main__":
    unittest.main()
