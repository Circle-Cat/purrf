from unittest import TestCase, main
from unittest.mock import patch, MagicMock, Mock
from backend.consumers.pubsub_puller import PubSubPuller, PullStatusResponse
from backend.common.constants import PullStatus, PUBSUB_PULL_MESSAGES_STATUS_KEY
from backend.common.asyncio_event_loop_manager import AsyncioEventLoopManager
from google.api_core.exceptions import NotFound
import concurrent.futures


class TestPubSubPuller(TestCase):
    def setUp(self):
        PubSubPuller._instances = {}
        self.project_id = "test-project"
        self.subscription_id = "test-subscription"
        self.subscription_path = "projects/test/subscriptions/sub"

    def test_singleton_pattern(self):
        """Verify that PubSubPuller maintains single instance per (project, subscription) pair."""
        puller1 = PubSubPuller(self.project_id, self.subscription_id)
        puller2 = PubSubPuller(self.project_id, self.subscription_id)

        self.assertIs(puller1, puller2)

        puller3 = PubSubPuller("another-project", "test-subscription")

        self.assertIsNot(puller1, puller3)

    @patch("backend.consumers.pubsub_puller.RedisClientFactory")
    def test_redis_client_unavailable(self, mock_factory):
        """Test proper error when Redis client cannot be created."""
        mock_factory().create_redis_client.return_value = None

        puller = PubSubPuller(self.project_id, self.subscription_id)

        with self.assertRaises(ValueError) as context:
            puller.check_pulling_messages_status()

        self.assertIn("Redis client not available", str(context.exception))

    @patch("backend.consumers.pubsub_puller.RedisClientFactory")
    def test_redis_status_not_found_and_not_pulling(self, mock_factory):
        """Test correct NOT_STARTED response when no Redis status found and not pulling locally."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {}
        mock_factory().create_redis_client.return_value = redis_client

        expected_result = PullStatusResponse(
            subscription_id=self.subscription_id,
            task_status=PullStatus.NOT_STARTED.code,
            message=PullStatus.NOT_STARTED.format_message(
                subscription_id=self.subscription_id
            ),
            timestamp=None,
        )

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.clear()
        puller._streaming_pull_future = None

        result = puller.check_pulling_messages_status()

        self.assertEqual(expected_result, result)

    @patch("backend.consumers.pubsub_puller.RedisClientFactory")
    def test_redis_status_not_found_but_local_is_pulling(self, mock_factory):
        """Test inconsistency error when locally pulling but no Redis status exists."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {}
        mock_factory().create_redis_client.return_value = redis_client
        mock_future = MagicMock()
        mock_future.done.return_value = False

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.set()
        puller._streaming_pull_future = mock_future

        with self.assertRaises(RuntimeError) as context:
            puller.check_pulling_messages_status()

        self.assertIn("Status inconsistency", str(context.exception))

    @patch("backend.consumers.pubsub_puller.RedisClientFactory")
    def test_redis_running_but_local_not_pulling(self, mock_factory):
        """Test inconsistency error when Redis reports running but locally not pulling."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {
            "task_status": PullStatus.RUNNING.code,
            "timestamp": "2024-05-28T12:00:00Z",
            "message": "Running normally",
        }
        mock_factory().create_redis_client.return_value = redis_client

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.clear()
        puller._streaming_pull_future = None

        with self.assertRaises(RuntimeError) as context:
            puller.check_pulling_messages_status()

        self.assertIn("Status inconsistency", str(context.exception))

    @patch("backend.consumers.pubsub_puller.RedisClientFactory")
    def test_local_pulling_but_redis_not_running(self, mock_factory):
        """Test inconsistency error when locally pulling but Redis reports stopped."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {
            "task_status": PullStatus.STOPPED.code,
            "timestamp": "2024-05-28T12:00:00Z",
            "message": "Stopped",
        }
        mock_factory().create_redis_client.return_value = redis_client
        mock_future = MagicMock()
        mock_future.done.return_value = False

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.set()
        puller._streaming_pull_future = mock_future

        with self.assertRaises(RuntimeError) as context:
            puller.check_pulling_messages_status()

        self.assertIn("Status inconsistency", str(context.exception))

    @patch("backend.consumers.pubsub_puller.RedisClientFactory")
    def test_status_consistent_running(self, mock_factory):
        """Test successful status check when local and Redis states match (RUNNING)."""
        redis_client = MagicMock()
        redis_client.hgetall.return_value = {
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

        mock_factory().create_redis_client.return_value = redis_client
        mock_future = MagicMock()
        mock_future.done.return_value = False

        puller = PubSubPuller(self.project_id, self.subscription_id)

        puller._is_pulling.set()
        puller._streaming_pull_future = mock_future

        result = puller.check_pulling_messages_status()
        self.assertEqual(expected_result, result)

    @patch("backend.consumers.pubsub_puller.dt.datetime")
    @patch("backend.consumers.pubsub_puller.RedisClientFactory.create_redis_client")
    def test_update_redis_pull_status_success(
        self, mock_create_redis_client, mock_datetime
    ):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis

        expected_timestamp = "2024-01-01T12:00:00.000000Z"
        fake_now = Mock()
        fake_iso = Mock()
        fake_iso.replace.return_value = expected_timestamp

        fake_now.isoformat.return_value = fake_iso
        mock_datetime.now.return_value = fake_now

        expected_message = f"Pulling started for {self.subscription_id}."

        puller = PubSubPuller(self.project_id, self.subscription_id)
        puller._update_redis_pull_status(PullStatus.RUNNING)

        mock_redis.hset.assert_called_once_with(
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
    @patch("backend.consumers.pubsub_puller.RedisClientFactory.create_redis_client")
    def test_update_redis_pull_status_with_kwargs(
        self, mock_create_redis_client, mock_datetime
    ):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis

        expected_timestamp = "2024-01-01T12:00:00.000000Z"
        fake_now = Mock()
        fake_iso = Mock()
        fake_iso.replace.return_value = expected_timestamp

        fake_now.isoformat.return_value = fake_iso
        mock_datetime.now.return_value = fake_now

        error = "Test Error"
        expected_message = f"Pulling failed for {self.subscription_id}: {error}."

        puller = PubSubPuller(self.project_id, self.subscription_id)
        puller._update_redis_pull_status(PullStatus.FAILED, error=error)

        mock_redis.hset.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(
                subscription_id=self.subscription_id
            ),
            mapping={
                "task_status": PullStatus.FAILED.code,
                "timestamp": expected_timestamp,
                "message": expected_message,
            },
        )

    @patch("backend.consumers.pubsub_puller.RedisClientFactory.create_redis_client")
    def test_update_redis_pull_status_no_redis_client(
        self,
        mock_create_redis_client,
    ):
        mock_create_redis_client.return_value = None

        puller = PubSubPuller(self.project_id, self.subscription_id)

        with self.assertRaises(ValueError):
            puller._update_redis_pull_status(PullStatus.RUNNING)

        self.assertEqual(mock_create_redis_client.call_count, 3)

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_no_active_pull_future_is_done(
        self, mock_update_redis_pull_status, mock_check_pulling_messages_status
    ):
        puller = PubSubPuller(self.project_id, self.subscription_id)
        puller._streaming_pull_future = MagicMock()
        puller._streaming_pull_future.done.return_value = True
        puller._is_pulling.clear()

        puller.stop_pulling_messages()

        mock_check_pulling_messages_status.assert_called_once()
        mock_update_redis_pull_status.assert_not_called()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_stop_successfully(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        puller = PubSubPuller(self.project_id, self.subscription_id)
        mock_future = MagicMock()
        mock_future.done.return_value = False
        puller._streaming_pull_future = mock_future
        puller._is_pulling.set()

        puller.stop_pulling_messages()

        mock_future.cancel.assert_called_once()
        mock_future.result.assert_called_once()
        mock_update_status.assert_called_once_with(PullStatus.STOPPED)
        self.assertFalse(puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_called_once()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_cancelled_error(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        puller = PubSubPuller(self.project_id, self.subscription_id)
        mock_future = MagicMock()
        mock_future.done.return_value = False
        mock_future.result.side_effect = concurrent.futures.CancelledError()
        puller._streaming_pull_future = mock_future
        puller._is_pulling.set()

        puller.stop_pulling_messages()

        mock_update_status.assert_called_once_with(PullStatus.STOPPED)
        self.assertFalse(puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_called_once()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_timeout_error(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        puller = PubSubPuller(self.project_id, self.subscription_id)
        mock_future = MagicMock()
        mock_future.done.return_value = False
        mock_future.result.side_effect = concurrent.futures.TimeoutError("timeout")
        puller._streaming_pull_future = mock_future
        puller._is_pulling.set()

        with self.assertRaises(TimeoutError):
            puller.stop_pulling_messages()

        mock_update_status.assert_called_once_with(PullStatus.FAILED, error="timeout")
        self.assertFalse(puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_not_called()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_generic_exception(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        puller = PubSubPuller(self.project_id, self.subscription_id)
        mock_future = MagicMock()
        mock_future.done.return_value = False
        mock_future.result.side_effect = Exception("unexpected error")
        puller._streaming_pull_future = mock_future
        puller._is_pulling.set()

        with self.assertRaises(Exception):
            puller.stop_pulling_messages()

        mock_update_status.assert_called_once_with(
            PullStatus.FAILED, error="unexpected error"
        )
        self.assertFalse(puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_not_called()

    @patch.object(PubSubPuller, "check_pulling_messages_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    def test_flag_set_but_no_future(
        self, mock_update_status, mock_check_pulling_messages_status
    ):
        puller = PubSubPuller(self.project_id, self.subscription_id)
        puller._streaming_pull_future = None
        puller._is_pulling.set()

        puller.stop_pulling_messages()

        mock_update_status.assert_not_called()
        self.assertFalse(puller._is_pulling.is_set())
        mock_check_pulling_messages_status.assert_called_once()

    @patch("backend.consumers.pubsub_puller.GoogleClientFactory.create_subscriber_client")
    def test_check_subscription_exist_true(self, mock_create_subscriber_client):
        mock_subscriber = MagicMock()
        mock_create_subscriber_client.return_value = mock_subscriber

        mock_subscription_obj = Mock()
        mock_subscription_obj.name = mock_subscriber.subscription_path(
            self.project_id, self.subscription_id
        )
        mock_subscriber.get_subscription.return_value = mock_subscription_obj

        puller = PubSubPuller(self.project_id, self.subscription_id)
        result = puller._check_subscription_exist()
        self.assertTrue(result)

    @patch("backend.consumers.pubsub_puller.GoogleClientFactory.create_subscriber_client")
    def test_check_subscription_exist_false(self, mock_create_subscriber_client):
        mock_subscriber = MagicMock()
        mock_create_subscriber_client.return_value = mock_subscriber

        mock_subscriber.get_subscription.side_effect = NotFound(
            "Subscription not found"
        )

        puller = PubSubPuller(self.project_id, self.subscription_id)
        result = puller._check_subscription_exist()
        self.assertFalse(result)

    @patch("backend.consumers.pubsub_puller.RedisClientFactory.create_redis_client")
    def test_delete_redis_pull_status_key_success(self, mock_create_redis_client):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis

        puller = PubSubPuller(self.project_id, self.subscription_id)
        puller._delete_redis_pull_status()

        mock_redis.delete.assert_called_once_with(
            PUBSUB_PULL_MESSAGES_STATUS_KEY.format(subscription_id=self.subscription_id)
        )

    @patch("backend.consumers.pubsub_puller.RedisClientFactory.create_redis_client")
    def test_delete_redis_pull_status_no_redis_client(
        self,
        mock_create_redis_client,
    ):
        mock_create_redis_client.return_value = None

        puller = PubSubPuller(self.project_id, self.subscription_id)

        with self.assertRaises(ValueError):
            puller._delete_redis_pull_status()

        self.assertEqual(mock_create_redis_client.call_count, 3)

    @patch("backend.consumers.pubsub_puller.RedisClientFactory.create_redis_client")
    def test_delete_redis_pull_status_failed(
        self,
        mock_create_redis_client,
    ):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis
        mock_redis.delete.side_effect = Exception()

        puller = PubSubPuller(self.project_id, self.subscription_id)

        with self.assertRaises(Exception):
            puller._delete_redis_pull_status()

        self.assertEqual(mock_redis.delete.call_count, 3)

    @patch.object(PubSubPuller, "_update_redis_pull_status")
    @patch("backend.consumers.pubsub_puller.GoogleClientFactory.create_subscriber_client")
    def test_pull_target_success(
        self, mock_create_subscriber_client, mock_update_status
    ):
        mock_subscriber = MagicMock()
        mock_future = MagicMock()
        mock_subscriber.subscription_path.return_value = self.subscription_path
        mock_create_subscriber_client.return_value = mock_subscriber

        mock_future.result.side_effect = lambda: time.sleep(0.05)

        puller = PubSubPuller(self.project_id, self.subscription_id)
        self.assertFalse(puller._is_pulling.is_set())

        with patch.object(puller._is_pulling, "clear") as mock_clear:
            puller._pull_target(callback=Mock())

            mock_subscriber.subscription_path.assert_called_once()
            mock_subscriber.subscribe.assert_called_once()
            self.assertTrue(puller._is_pulling.is_set())
            mock_update_status.assert_called_with(PullStatus.RUNNING)

            mock_clear.assert_called_once()

    @patch.object(PubSubPuller, "_delete_redis_pull_status")
    @patch.object(PubSubPuller, "_update_redis_pull_status")
    @patch("backend.consumers.pubsub_puller.GoogleClientFactory.create_subscriber_client")
    def test_pull_target_with_not_found_error(
        self, mock_create_subscriber_client, mock_update_status, mock_delete_status
    ):
        mock_subscriber = MagicMock()
        mock_future = MagicMock()
        mock_subscriber.subscription_path.return_value = self.subscription_path
        mock_create_subscriber_client.return_value = mock_subscriber
        mock_subscriber.subscribe.side_effect = NotFound("Subscription not found")

        puller = PubSubPuller(self.project_id, self.subscription_id)
        self.assertFalse(puller._is_pulling.is_set())

        with patch.object(puller._is_pulling, "clear") as mock_clear:
            puller._pull_target(callback=Mock())

            mock_subscriber.subscription_path.assert_called_once()
            mock_subscriber.subscribe.assert_called_once()
            self.assertFalse(puller._is_pulling.is_set())
            mock_update_status.assert_not_called()
            mock_delete_status.assert_called_once()
            mock_clear.assert_not_called()

    @patch.object(PubSubPuller, "_update_redis_pull_status")
    @patch("backend.consumers.pubsub_puller.GoogleClientFactory.create_subscriber_client")
    def test_pull_target_with_expection(
        self, mock_create_subscriber_client, mock_update_status
    ):
        mock_future = MagicMock()
        mock_future.result.side_effect = Exception("unexpected error")

        mock_subscriber = MagicMock()
        mock_subscriber.subscribe.return_value = mock_future
        mock_subscriber.subscription_path.return_value = self.subscription_path
        mock_create_subscriber_client.return_value = mock_subscriber

        puller = PubSubPuller(self.project_id, self.subscription_id)

        self.assertFalse(puller._is_pulling.is_set())

        with patch.object(puller._is_pulling, "clear") as mock_clear:
            puller._pull_target(callback=Mock())

            mock_subscriber.subscription_path.assert_called_once()
            mock_subscriber.subscribe.assert_called_once()
            self.assertTrue(puller._is_pulling.is_set())
            mock_update_status.assert_any_call(PullStatus.RUNNING)
            mock_update_status.assert_any_call(
                PullStatus.FAILED, error="unexpected error"
            )
            mock_clear.assert_called_once()

    @patch.object(PubSubPuller, "_check_subscription_exist", return_value=True)
    @patch("backend.consumers.pubsub_puller.GoogleClientFactory.create_subscriber_client")
    @patch("backend.consumers.pubsub_puller.threading.Thread")
    def test_start_pulling_messages_success(
        self, mock_thread, mock_create_subscriber_client, mock_check_subscription_exist
    ):
        mock_subscriber = MagicMock()
        mock_create_subscriber_client.return_value = mock_subscriber
        mock_future = Mock(spec=concurrent.futures.Future)
        mock_subscriber.subscribe.return_value = mock_future

        mock_callback = Mock()

        puller = PubSubPuller(self.project_id, self.subscription_id)
        self.assertFalse(puller._is_pulling.is_set())

        puller.start_pulling_messages(mock_callback)

        mock_check_subscription_exist.assert_called_once()
        mock_thread.assert_called_once()

        self.assertTrue(mock_thread.call_args[1].get("daemon"))
        mock_thread.return_value.start.assert_called_once()

    @patch.object(PubSubPuller, "_check_subscription_exist", return_value=False)
    def test_start_pulling_messages_subscription_not_exist(
        self, mock_check_subscription_exist
    ):
        mock_callback = Mock()

        puller = PubSubPuller(self.project_id, self.subscription_id)

        with self.assertRaises(ValueError):
            puller.start_pulling_messages(mock_callback)

        mock_check_subscription_exist.assert_called_once()
        self.assertFalse(puller._is_pulling.is_set())

    def test_start_pulling_messages_no_callback(self):
        puller = PubSubPuller(self.project_id, self.subscription_id)
        with self.assertRaises(ValueError):
            puller.start_pulling_messages(None)

        self.assertFalse(puller._is_pulling.is_set())

    @patch.object(PubSubPuller, "_check_subscription_exist", return_value=True)
    @patch("backend.consumers.pubsub_puller.GoogleClientFactory.create_subscriber_client")
    @patch("backend.consumers.pubsub_puller.threading.Thread")
    def test_start_pulling_messages_already_pulling(
        self, mock_thread, mock_create_subscriber_client, mock_check_subscription_exist
    ):
        puller = PubSubPuller(self.project_id, self.subscription_id)

        mock_future = MagicMock()
        mock_future.done.return_value = False
        puller._streaming_pull_future = mock_future

        puller._is_pulling.set()

        mock_callback = Mock()

        puller.start_pulling_messages(mock_callback)

        mock_check_subscription_exist.assert_called_once()
        mock_thread.assert_not_called()
        mock_create_subscriber_client.assert_not_called()

    @patch.object(PubSubPuller, "stop_pulling_messages")
    @patch.object(PubSubPuller, "_check_subscription_exist", return_value=True)
    @patch("backend.consumers.pubsub_puller.GoogleClientFactory.create_subscriber_client")
    @patch("backend.consumers.pubsub_puller.threading.Thread")
    def test_start_pulling_messages_stale(
        self,
        mock_thread,
        mock_create_subscriber_client,
        mock_check_subscription_exist,
        mock_stop_pulling_messages,
    ):
        puller = PubSubPuller(self.project_id, self.subscription_id)

        mock_future = MagicMock()
        mock_future.done.return_value = False
        puller._streaming_pull_future = mock_future

        mock_callback = Mock()

        puller.start_pulling_messages(mock_callback)

        mock_check_subscription_exist.assert_called_once()
        mock_thread.assert_called_once()
        mock_stop_pulling_messages.assert_called_once()

    def test_wrap_sync_callback_returns_original(self):
        def sync_callback(msg):
            return f"processed {msg}"

        puller = PubSubPuller(self.project_id, self.subscription_id)

        wrapped = puller._wrap_callback_if_async(sync_callback)
        self.assertIs(wrapped, sync_callback)

    @patch.object(AsyncioEventLoopManager, "run_async_in_background_loop")
    def test_wrap_async_callback_returns_wrapped(self, mock_run_in_loop):
        async def async_callback(msg):
            return f"processed {msg}"

        mock_run_in_loop.return_value = "done"

        puller = PubSubPuller(self.project_id, self.subscription_id)
        wrapped = puller._wrap_callback_if_async(async_callback)

        self.assertTrue(callable(wrapped))
        self.assertNotEqual(wrapped, async_callback)

        result = wrapped("message")
        mock_run_in_loop.assert_called_once()
        self.assertEqual(result, "done")


if __name__ == "__main__":
    main()
