import inspect
from unittest import TestCase, main
from unittest.mock import patch, MagicMock, Mock
from backend.consumers.pubsub_puller import PubSubPuller, PullStatusResponse
from backend.common.constants import PullStatus, PUBSUB_PULL_MESSAGES_STATUS_KEY
from google.api_core.exceptions import NotFound
import concurrent.futures
import datetime as dt


class TestPubSubPuller(TestCase):
    def setUp(self):
        self.project_id = "test-project"
        self.subscription_id = "test-subscription"
        self.subscription_path = (
            f"projects/{self.project_id}/subscriptions/{self.subscription_id}"
        )

        self.mock_logger = MagicMock()
        self.mock_redis_client = MagicMock()
        self.mock_subscriber_client = MagicMock()
        self.mock_asyncio_event_loop_manager = MagicMock()

        self.puller = PubSubPuller(
            project_id=self.project_id,
            subscription_id=self.subscription_id,
            logger=self.mock_logger,
            redis_client=self.mock_redis_client,
            subscriber_client=self.mock_subscriber_client,
            asyncio_event_loop_manager=self.mock_asyncio_event_loop_manager,
        )

        self.mock_subscriber_client.subscription_path.return_value = (
            self.subscription_path
        )

    def test_redis_status_not_found_and_not_pulling(self):
        """Test correct NOT_STARTED response when no Redis status found and not pulling locally."""
        self.mock_redis_client.hgetall.return_value = {}

        expected_result = PullStatusResponse(
            subscription_id=self.subscription_id,
            task_status=PullStatus.NOT_STARTED.code,
            message=PullStatus.NOT_STARTED.format_message(
                subscription_id=self.subscription_id
            ),
            timestamp=None,
        )

        self.puller._is_pulling.clear()
        self.puller._streaming_pull_future = None

        result = self.puller.check_pulling_messages_status()

        self.assertEqual(expected_result, result)
        self.mock_redis_client.hgetall.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(subscription_id=self.subscription_id)
        )

    def test_redis_status_not_found_but_local_is_pulling(self):
        """Test inconsistency error when locally pulling but no Redis status exists."""
        self.mock_redis_client.hgetall.return_value = {}
        mock_future = MagicMock()
        mock_future.done.return_value = False

        self.puller._is_pulling.set()
        self.puller._streaming_pull_future = mock_future

        with self.assertRaises(RuntimeError):
            self.puller.check_pulling_messages_status()

        self.mock_redis_client.hgetall.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(subscription_id=self.subscription_id)
        )

    def test_redis_running_but_local_not_pulling(self):
        """Test inconsistency error when Redis reports running but locally not pulling."""
        self.mock_redis_client.hgetall.return_value = {
            "task_status": PullStatus.RUNNING.code,
            "timestamp": "2024-05-28T12:00:00Z",
            "message": "Running normally",
        }

        self.puller._is_pulling.clear()
        self.puller._streaming_pull_future = None

        with self.assertRaises(RuntimeError):
            self.puller.check_pulling_messages_status()

        self.mock_redis_client.hgetall.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(subscription_id=self.subscription_id)
        )

    def test_local_pulling_but_redis_not_running(self):
        """Test inconsistency error when locally pulling but Redis reports stopped."""
        self.mock_redis_client.hgetall.return_value = {
            "task_status": PullStatus.STOPPED.code,
            "timestamp": "2024-05-28T12:00:00Z",
            "message": "Stopped",
        }
        mock_future = MagicMock()
        mock_future.done.return_value = False

        self.puller._is_pulling.set()
        self.puller._streaming_pull_future = mock_future

        with self.assertRaises(RuntimeError):
            self.puller.check_pulling_messages_status()

        self.mock_redis_client.hgetall.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(subscription_id=self.subscription_id)
        )

    def test_status_consistent_running(self):
        """Test successful status check when local and Redis states match (RUNNING)."""
        self.mock_redis_client.hgetall.return_value = {
            "task_status": PullStatus.RUNNING.code,
            "timestamp": "2024-05-28T12:00:00Z",
            "message": PullStatus.RUNNING.format_message(
                subscription_id=self.subscription_id
            ),
        }
        expected_result = PullStatusResponse(
            subscription_id=self.subscription_id,
            task_status=PullStatus.RUNNING.code,
            message=PullStatus.RUNNING.format_message(
                subscription_id=self.subscription_id
            ),
            timestamp="2024-05-28T12:00:00Z",
        )

        mock_future = MagicMock()
        mock_future.done.return_value = False

        self.puller._is_pulling.set()
        self.puller._streaming_pull_future = mock_future

        result = self.puller.check_pulling_messages_status()
        self.assertEqual(expected_result, result)
        self.mock_redis_client.hgetall.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(subscription_id=self.subscription_id)
        )

    @patch("backend.consumers.pubsub_puller.dt.datetime")
    def test_update_redis_pull_status_success(self, mock_datetime):
        expected_timestamp = "2024-01-01T12:00:00.000000Z"
        fake_now = Mock()
        fake_iso = Mock()
        fake_iso.replace.return_value = expected_timestamp

        fake_now.isoformat.return_value = fake_iso
        mock_datetime.now.return_value = fake_now
        mock_datetime.timezone.utc = dt.timezone.utc

        expected_message = f"Pulling started for {self.subscription_id}."

        self.puller._update_redis_pull_status(PullStatus.RUNNING)

        self.mock_redis_client.hset.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(
                subscription_id=self.subscription_id
            ),
            mapping={
                "task_status": PullStatus.RUNNING.code,
                "timestamp": expected_timestamp,
                "message": expected_message,
            },
        )

    @patch("backend.consumers.pubsub_puller.dt.datetime")
    def test_update_redis_pull_status_with_kwargs(self, mock_datetime):
        expected_timestamp = "2024-01-01T12:00:00.000000Z"
        fake_now = Mock()
        fake_iso = Mock()
        fake_iso.replace.return_value = expected_timestamp

        fake_now.isoformat.return_value = fake_iso
        mock_datetime.now.return_value = fake_now
        mock_datetime.timezone.utc = dt.timezone.utc

        error = "Test Error"
        expected_message = f"Pulling failed for {self.subscription_id}: {error}."

        self.puller._update_redis_pull_status(PullStatus.FAILED, error=error)

        self.mock_redis_client.hset.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(
                subscription_id=self.subscription_id
            ),
            mapping={
                "task_status": PullStatus.FAILED.code,
                "timestamp": expected_timestamp,
                "message": expected_message,
            },
        )

    def test_update_redis_pull_status_failed_logs_error(self):
        self.mock_redis_client.hset.side_effect = Exception("Redis connection lost")

        self.puller._update_redis_pull_status(PullStatus.RUNNING)

        self.mock_logger.error.assert_called_once()
        self.assertIn(
            "Failed to update Redis status", self.mock_logger.error.call_args[0][0]
        )

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_no_active_pull_future_is_done(
        self, mock_update_redis_pull_status, mock_check_pulling_messages_status
    ):
        self.puller._streaming_pull_future = MagicMock()
        self.puller._streaming_pull_future.done.return_value = True
        self.puller._is_pulling.clear()

        self.puller.stop_pulling_messages()

        mock_check_pulling_messages_status.assert_called_once()
        mock_update_redis_pull_status.assert_not_called()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_stop_successfully(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        mock_future = MagicMock()
        mock_future.done.return_value = False
        self.puller._streaming_pull_future = mock_future
        self.puller._is_pulling.set()

        self.puller.stop_pulling_messages()

        mock_future.cancel.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=3)
        mock_update_status.assert_called_once_with(PullStatus.STOPPED)
        self.assertFalse(self.puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_called_once()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_cancelled_error(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        mock_future = MagicMock()
        mock_future.done.return_value = False
        mock_future.result.side_effect = concurrent.futures.CancelledError()
        self.puller._streaming_pull_future = mock_future
        self.puller._is_pulling.set()

        self.puller.stop_pulling_messages()

        mock_future.cancel.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=3)
        mock_update_status.assert_called_once_with(PullStatus.STOPPED)
        self.assertFalse(self.puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_called_once()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_timeout_error_on_stop(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        mock_future = MagicMock()
        mock_future.done.return_value = False
        mock_future.result.side_effect = concurrent.futures.TimeoutError("timeout")
        self.puller._streaming_pull_future = mock_future
        self.puller._is_pulling.set()

        with self.assertRaises(TimeoutError):
            self.puller.stop_pulling_messages()

        mock_future.cancel.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=3)
        mock_update_status.assert_called_once_with(PullStatus.FAILED, error="timeout")
        self.assertFalse(self.puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_not_called()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_generic_exception_on_stop(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        mock_future = MagicMock()
        mock_future.done.return_value = False
        mock_future.result.side_effect = Exception("unexpected error")
        self.puller._streaming_pull_future = mock_future
        self.puller._is_pulling.set()

        with self.assertRaises(Exception):
            self.puller.stop_pulling_messages()

        mock_future.cancel.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=3)
        mock_update_status.assert_called_once_with(
            PullStatus.FAILED, error="unexpected error"
        )
        self.assertFalse(self.puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_not_called()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_flag_set_but_no_future(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        self.puller._streaming_pull_future = None
        self.puller._is_pulling.set()

        self.puller.stop_pulling_messages()

        mock_update_status.assert_not_called()
        self.assertFalse(self.puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_called_once()

    def test_check_subscription_exist_true(self):
        self.mock_subscriber_client.get_subscription.return_value = MagicMock()

        result = self.puller._check_subscription_exist()
        self.assertTrue(result)
        self.mock_subscriber_client.subscription_path.assert_called_once_with(
            self.project_id, self.subscription_id
        )
        self.mock_subscriber_client.get_subscription.assert_called_once_with(
            subscription=self.subscription_path
        )

    def test_check_subscription_exist_false(self):
        self.mock_subscriber_client.get_subscription.side_effect = NotFound(
            "Subscription not found"
        )

        result = self.puller._check_subscription_exist()
        self.assertFalse(result)
        self.mock_subscriber_client.subscription_path.assert_called_once_with(
            self.project_id, self.subscription_id
        )
        self.mock_subscriber_client.get_subscription.assert_called_once_with(
            subscription=self.subscription_path
        )

    def test_delete_redis_pull_status_key_success(self):
        self.puller._delete_redis_pull_status()

        self.mock_redis_client.delete.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(subscription_id=self.subscription_id)
        )

    def test_delete_redis_pull_status_failed(self):
        self.mock_redis_client.delete.side_effect = Exception("Redis error")

        with self.assertRaises(RuntimeError):
            self.puller._delete_redis_pull_status()

        self.mock_redis_client.delete.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(subscription_id=self.subscription_id)
        )

    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_pull_target_success(self, mock_update_status):
        mock_future = MagicMock()
        mock_future.result.side_effect = None
        self.mock_subscriber_client.subscribe.return_value = mock_future

        self.assertFalse(self.puller._is_pulling.is_set())

        with patch.object(self.puller._is_pulling, "clear") as mock_clear:
            self.puller._pull_target(callback=Mock())

            self.mock_subscriber_client.subscription_path.assert_called_once_with(
                self.project_id, self.subscription_id
            )
            self.mock_subscriber_client.subscribe.assert_called_once()
            self.assertTrue(self.puller._is_pulling.is_set())
            mock_update_status.assert_called_with(PullStatus.RUNNING)
            mock_future.result.assert_called_once()

            mock_clear.assert_called_once()

    @patch.object(PubSubPuller, "_delete_redis_pull_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_pull_target_with_not_found_error(
        self, mock_update_status, mock_delete_status
    ):
        self.mock_subscriber_client.subscribe.side_effect = NotFound(
            "Subscription not found"
        )

        self.assertFalse(self.puller._is_pulling.is_set())

        with patch.object(self.puller._is_pulling, "clear") as mock_clear:
            self.puller._pull_target(callback=Mock())

            self.mock_subscriber_client.subscription_path.assert_called_once_with(
                self.project_id, self.subscription_id
            )
            self.mock_subscriber_client.subscribe.assert_called_once()
            self.assertFalse(
                self.puller._is_pulling.is_set()
            )  # Should not be set if NotFound occurs before that
            mock_update_status.assert_not_called()
            mock_delete_status.assert_called_once()
            mock_clear.assert_not_called()  # Finally block ensures it's clear, but explicit clear might not happen for this path.

    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_pull_target_with_exception(self, mock_update_status):
        mock_future = MagicMock()
        mock_future.result.side_effect = Exception("unexpected error")

        self.mock_subscriber_client.subscribe.return_value = mock_future

        self.assertFalse(self.puller._is_pulling.is_set())

        with patch.object(self.puller._is_pulling, "clear") as mock_clear:
            self.puller._pull_target(callback=Mock())

            self.mock_subscriber_client.subscription_path.assert_called_once_with(
                self.project_id, self.subscription_id
            )
            self.mock_subscriber_client.subscribe.assert_called_once()
            self.assertTrue(
                self.puller._is_pulling.is_set()
            )  # Should be set before exception in .result()
            mock_update_status.assert_any_call(PullStatus.RUNNING)
            mock_update_status.assert_any_call(
                PullStatus.FAILED, error="unexpected error"
            )
            mock_clear.assert_called_once()

    @patch.object(PubSubPuller, "_check_subscription_exist", return_value=True)
    @patch("backend.consumers.pubsub_puller.threading.Thread")
    def test_start_pulling_messages_success(
        self, mock_thread, mock_check_subscription_exist
    ):
        mock_callback = Mock()

        # The actual subscribe call happens inside _pull_target, mocked here for _pull_target
        mock_future = Mock(spec=concurrent.futures.Future)
        self.mock_subscriber_client.subscribe.return_value = mock_future

        self.assertFalse(self.puller._is_pulling.is_set())

        self.puller.start_pulling_messages(mock_callback)

        mock_check_subscription_exist.assert_called_once()
        mock_thread.assert_called_once()

        self.assertEqual(mock_thread.call_args[1].get("daemon"), True)
        mock_thread.return_value.start.assert_called_once()

    @patch.object(PubSubPuller, "_check_subscription_exist", return_value=False)
    def test_start_pulling_messages_subscription_not_exist(
        self, mock_check_subscription_exist
    ):
        mock_callback = Mock()

        with self.assertRaises(ValueError):
            self.puller.start_pulling_messages(mock_callback)

        mock_check_subscription_exist.assert_called_once()
        self.assertFalse(self.puller._is_pulling.is_set())

    def test_start_pulling_messages_no_callback(self):
        with self.assertRaises(ValueError):
            self.puller.start_pulling_messages(None)

        self.assertFalse(self.puller._is_pulling.is_set())

    @patch.object(PubSubPuller, "_check_subscription_exist", return_value=True)
    @patch("backend.consumers.pubsub_puller.threading.Thread")
    def test_start_pulling_messages_already_pulling(
        self, mock_thread, mock_check_subscription_exist
    ):
        mock_future = MagicMock()
        mock_future.done.return_value = False
        self.puller._streaming_pull_future = mock_future

        self.puller._is_pulling.set()

        mock_callback = Mock()

        self.puller.start_pulling_messages(mock_callback)

        mock_check_subscription_exist.assert_called_once()
        mock_thread.assert_not_called()

    @patch.object(PubSubPuller, "stop_pulling_messages")
    @patch.object(PubSubPuller, "_check_subscription_exist", return_value=True)
    @patch("backend.consumers.pubsub_puller.threading.Thread")
    def test_start_pulling_messages_stale_future(
        self,
        mock_thread,
        mock_check_subscription_exist,
        mock_stop_pulling_messages,
    ):
        mock_future = MagicMock()
        mock_future.done.return_value = False
        self.puller._streaming_pull_future = mock_future
        self.puller._is_pulling.clear()

        mock_callback = Mock()

        self.puller.start_pulling_messages(mock_callback)

        mock_check_subscription_exist.assert_called_once()

        mock_stop_pulling_messages.assert_called_once()
        mock_thread.assert_called_once()

    def test_wrap_sync_callback_returns_original(self):
        def sync_callback(msg):
            return f"processed {msg}"

        wrapped = self.puller._wrap_callback_if_async(sync_callback)
        self.assertIs(wrapped, sync_callback)

    def test_wrap_async_callback_returns_wrapped(self):
        async def async_callback(msg):
            return f"processed {msg}"

        self.mock_asyncio_event_loop_manager.run_async_in_background_loop.return_value = "done"

        wrapped = self.puller._wrap_callback_if_async(async_callback)

        self.assertTrue(callable(wrapped))
        self.assertIsNot(
            wrapped, async_callback
        )  # Should be a wrapper, not the original

        result = wrapped("message")
        # The wrapper lambda should call run_async_in_background_loop with the async_callback coroutine
        # and the message argument. The actual coroutine is `async_callback(msg)`.
        self.mock_asyncio_event_loop_manager.run_async_in_background_loop.assert_called_once()
        # Check the type of the argument passed to run_async_in_background_loop
        # It should be a coroutine object.
        called_arg = (
            self.mock_asyncio_event_loop_manager.run_async_in_background_loop.call_args[
                0
            ][0]
        )

        self.assertTrue(inspect.iscoroutine(called_arg))
        self.assertEqual(result, "done")


if __name__ == "__main__":
    main()
