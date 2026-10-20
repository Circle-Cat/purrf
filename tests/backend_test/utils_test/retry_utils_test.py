import unittest
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from tenacity import AsyncRetrying, Retrying, wait_none
from unittest import TestCase, main
from unittest.mock import MagicMock
from backend.utils.retry_utils import RetryUtils


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


class TestRetryUtilsAsync(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.retry_utils = RetryUtils()

    def test_get_async_retry_on_transient_returns_async_retrying_instance(self):
        retrier = self.retry_utils.get_async_retry_on_transient
        self.assertIsInstance(retrier, AsyncRetrying)

    def test_get_async_retry_on_transient_returns_new_instance_each_time(self):
        """Each access returns a fresh instance to avoid shared state in concurrent calls."""
        retrier_a = self.retry_utils.get_async_retry_on_transient
        retrier_b = self.retry_utils.get_async_retry_on_transient
        self.assertIsNot(retrier_a, retrier_b)

    async def test_get_async_retry_on_transient_executes_successfully(self):
        mock_func = MagicMock(return_value="ok")

        result = None
        async for attempt in self.retry_utils.get_async_retry_on_transient:
            with attempt:
                result = mock_func()

        self.assertEqual(result, "ok")
        self.assertEqual(mock_func.call_count, 1)

    async def test_get_async_retry_on_transient_retries_on_general_exception(self):
        mock_func = MagicMock(side_effect=[IOError("transient"), None])

        async for attempt in self.retry_utils.get_async_retry_on_transient:
            with attempt:
                mock_func()

        self.assertEqual(mock_func.call_count, 2)

    async def test_get_async_retry_on_transient_stops_after_three_attempts(self):
        mock_func = MagicMock(
            side_effect=[Exception("1"), Exception("2"), Exception("3")]
        )

        with self.assertRaises(Exception):
            async for attempt in self.retry_utils.get_async_retry_on_transient:
                with attempt:
                    mock_func()

        self.assertEqual(mock_func.call_count, 3)

    async def test_get_async_retry_on_transient_does_not_retry_on_value_error(self):
        mock_func = MagicMock(side_effect=ValueError("invalid"))

        with self.assertRaises(ValueError):
            async for attempt in self.retry_utils.get_async_retry_on_transient:
                with attempt:
                    mock_func()

        self.assertEqual(mock_func.call_count, 1)


def _flaky_pipeline(failures):
    """A real redis-py pipeline whose first ``failures`` sends raise.

    Only the wire is faked: queuing, ``execute`` and the ``reset`` that empties
    the command stack afterwards are redis-py's own. Returns the pipeline and
    the list of command batches each attempt actually sent.
    """
    pipeline = Redis().pipeline()
    connection = MagicMock()
    connection.retry.call_with_retry = lambda do, fail: do()
    pipeline.connection_pool.get_connection = MagicMock(return_value=connection)
    pipeline.connection_pool.release = MagicMock()
    sent = []

    def send(conn, commands, raise_on_error):
        sent.append([args for args, _ in commands])
        if len(sent) <= failures:
            raise RedisConnectionError("connection reset")
        return [f"value of {args[1]}" for args, _ in commands]

    pipeline._execute_transaction = send
    return pipeline, sent


class TestExecutePipeline(TestCase):
    def setUp(self):
        self.retry_utils = RetryUtils()
        self.retry_utils._retry_on_transient = (
            self.retry_utils._retry_on_transient.copy(wait=wait_none())
        )

    def test_retrying_the_bound_execute_sends_nothing_the_second_time(self):
        """Why execute_pipeline exists: redis-py empties the command stack
        when execute finishes, even on failure, so a retry of the same bound
        method replays an empty pipeline and quietly answers []. If redis-py
        stops doing that, this fails and the helper can be revisited."""
        pipeline, sent = _flaky_pipeline(failures=1)
        pipeline.get("a")

        result = self.retry_utils.get_retry_on_transient(pipeline.execute)

        self.assertEqual(result, [])
        self.assertEqual(sent, [[("GET", "a")]])

    def test_a_retry_resends_every_queued_command(self):
        pipeline, sent = _flaky_pipeline(failures=1)
        pipeline.get("a")
        pipeline.get("b")

        result = self.retry_utils.execute_pipeline(pipeline)

        self.assertEqual(result, ["value of a", "value of b"])
        self.assertEqual(sent, [[("GET", "a"), ("GET", "b")]] * 2)

    def test_gives_up_after_three_attempts(self):
        pipeline, sent = _flaky_pipeline(failures=3)
        pipeline.get("a")

        with self.assertRaises(RedisConnectionError):
            self.retry_utils.execute_pipeline(pipeline)
        self.assertEqual(len(sent), 3)

    def test_an_empty_pipeline_sends_nothing(self):
        pipeline, sent = _flaky_pipeline(failures=0)

        self.assertEqual(self.retry_utils.execute_pipeline(pipeline), [])
        self.assertEqual(sent, [])


if __name__ == "__main__":
    main()
