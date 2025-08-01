from tenacity import Retrying
from unittest import TestCase, main
from unittest.mock import MagicMock
from src.utils.retry_utils import RetryUtils


class TestRetryUtils(TestCase):
    def setUp(self):
        self.retry_utils = RetryUtils()

    def test_get_retry_on_transient_returns_retrying_instance(self):
        retrier = self.retry_utils.get_retry_on_transient
        self.assertIsInstance(retrier, Retrying)

    def test_get_retry_on_transient_stops_after_attempts(self):
        retrier = self.retry_utils.get_retry_on_transient
        mock_func = MagicMock(
            side_effect=[
                Exception("Attempt 1"),
                Exception("Attempt 2"),
                Exception("Attempt 3"),
            ]
        )

        with self.assertRaises(Exception):
            for attempt in retrier:
                with attempt:
                    mock_func()

        self.assertEqual(mock_func.call_count, 3)

    def test_get_retry_on_transient_retries_on_general_exception(self):
        retrier = self.retry_utils.get_retry_on_transient
        mock_func = MagicMock(
            side_effect=[IOError("Network error"), None]
        )  # Fails once, then succeeds

        for attempt in retrier:
            with attempt:
                mock_func()

        self.assertEqual(
            mock_func.call_count, 2
        )  # Called once for failure, once for success

    def test_get_retry_on_transient_does_not_retry_on_value_error(self):
        retrier = self.retry_utils.get_retry_on_transient
        mock_func = MagicMock(side_effect=ValueError("Invalid input"))

        with self.assertRaises(ValueError):
            for attempt in retrier:
                with attempt:
                    mock_func()

        self.assertEqual(mock_func.call_count, 1)  # Called only once

    def test_get_retry_on_transient_executes_successfully(self):
        retrier = self.retry_utils.get_retry_on_transient
        mock_func = MagicMock(return_value="Success")

        result = None
        for attempt in retrier:
            with attempt:
                result = mock_func()

        self.assertEqual(result, "Success")
        self.assertEqual(mock_func.call_count, 1)  # Called only once


if __name__ == "__main__":
    main()
