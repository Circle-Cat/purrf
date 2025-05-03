import logging
import os
import unittest
from unittest.mock import patch
from src.common.logger import get_logger
import src.common.logger as logger_module
from io import StringIO
from src.common.environment_constants import LOG_LEVEL


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

    def test_log_format(self):
        with patch.dict(os.environ, {LOG_LEVEL: "INFO"}):
            get_logger()
            log_capture_string = StringIO()
            root_logger = logging.getLogger()
            if root_logger.handlers:
                root_logger.handlers[0].stream = log_capture_string
            else:
                ch = logging.StreamHandler(log_capture_string)
                logging.getLogger().addHandler(ch)

            logging.info("Test message")
            log_contents = log_capture_string.getvalue()
            expected_format = (
                r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - INFO - Test message\n"
            )
            self.assertRegex(log_contents, expected_format)

    def test_setup_logger_called_once(self):
        with patch("logging.basicConfig") as mock_basic_config:
            get_logger()
            get_logger()
            get_logger()

            mock_basic_config.assert_called_once()


if __name__ == "__main__":
    unittest.main()
