import logging
import os
import unittest
from unittest.mock import patch
from tools.log.logger import setup_logger
from io import StringIO


class TestLogger(unittest.TestCase):
    def setUp(self):
        logging.getLogger().handlers = []
        logging.getLogger().setLevel(logging.NOTSET)

    def tearDown(self):
        logging.getLogger().handlers = []

    def test_default_log_level(self):
        setup_logger()
        self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.INFO)

    def test_custom_log_level(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            setup_logger()
            self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.DEBUG)

    def test_invalid_log_level(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}):
            setup_logger()
            self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.INFO)

    def test_log_format(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}):
            setup_logger()
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


if __name__ == "__main__":
    unittest.main()
