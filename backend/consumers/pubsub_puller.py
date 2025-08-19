from google.api_core.exceptions import NotFound
from backend.common.redis_client import RedisClientFactory
from backend.common.google_client import GoogleClientFactory
from backend.common.constants import PullStatus, PUBSUB_PULL_MESSAGES_STATUS_KEY
from backend.common.asyncio_event_loop_manager import AsyncioEventLoopManager
from backend.common.logger import get_logger
from dataclasses import dataclass
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import concurrent.futures
import datetime as dt
import threading
import inspect

logger = get_logger()


@dataclass
class PullStatusResponse:
    subscription_id: str
    task_status: str
    message: str
    timestamp: str | None


class PubSubPuller:
    """
    Manages asynchronous message pulling from Google Cloud Pub/Sub subscriptions.
    Implements a singleton pattern per project_id-subscription_id pair.
    """

    _instances = {}

    @classmethod
    def make_instance_key(cls, project_id: str, subscription_id: str) -> str:
        return f"{project_id}-{subscription_id}"

    def __new__(cls, project_id: str, subscription_id: str):
        """
        Implement the singleton pattern to ensure that there is only one PubSubPuller instance for each project_id-subscription_id pair.
        """
        key = cls.make_instance_key(project_id, subscription_id)
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)
        return cls._instances[key]

    def __init__(self, project_id: str, subscription_id: str):
        """
        Initialize the PubSubPuller instance.
        """
        if not hasattr(self, "_initialized") or not self._initialized:
            self.project_id = project_id
            self.subscription_id = subscription_id
            self._streaming_pull_future: concurrent.futures.Future = None
            self._is_pulling = threading.Event()
            self._lock = threading.RLock()
            self._pull_exception = False
            self._initialized = True

            key = self.make_instance_key(self.project_id, self.subscription_id)
            logger.info(f"Initialized PubSubPuller for {key}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _update_redis_pull_status(self, status: PullStatus, **kwargs):
        """
        Updates the pull status in Redis Hash using a PullStatus enum and dynamic message formatting.
        """
        redis_client = RedisClientFactory().create_redis_client()
        if not redis_client:
            raise ValueError("Redis client not available. Cannot update pull status.")
        timestamp = (
            dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        try:
            message = status.format_message(
                subscription_id=self.subscription_id, **kwargs
            )
            status_redis_key = PUBSUB_PULL_MESSAGES_STATUS_KEY.format(
                subscription_id=self.subscription_id
            )
            redis_client.hset(
                status_redis_key,
                mapping={
                    "task_status": status.code,
                    "timestamp": timestamp,
                    "message": message,
                },
            )
            logger.debug(
                f"Redis status updated for {self.subscription_id}: {status.code}"
            )
        except Exception as e:
            logger.error(
                f"Failed to update Redis status for {self.subscription_id}: {e}"
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _delete_redis_pull_status(self):
        """
        Deleted the pull status in Redis Hash.
        """
        redis_client = RedisClientFactory().create_redis_client()
        if not redis_client:
            raise ValueError(
                "Redis client not available. Cannot delete obsolete pull status."
            )
        try:
            status_redis_key = PUBSUB_PULL_MESSAGES_STATUS_KEY.format(
                subscription_id=self.subscription_id
            )
            redis_client.delete(status_redis_key)
            logger.debug(f"Redis status deleted for {self.subscription_id}")
        except Exception as e:
            logger.error(
                f"Failed to delete Redis status for {self.subscription_id}: {e}"
            )
            raise RuntimeError(
                f"Failed to delete Redis status for {self.subscription_id}"
            )

    def _wrap_callback_if_async(self, callback):
        """
        Wrap async callbacks to run in the background event loop.

        If the callback is a coroutine function, wrap it to run using
        AsyncioEventLoopManager. Otherwise, return it as-is.

        Args:
            callback (Callable): The original callback function.

        Returns:
            Callable: A sync wrapper if async, or the original callback.
        """

        if inspect.iscoroutinefunction(callback):
            loop_mgr = AsyncioEventLoopManager()
            return lambda msg: loop_mgr.run_async_in_background_loop(callback(msg))
        return callback

    def _pull_target(self, callback):
        """
        Internal method that runs the message pulling logic in a background thread.

        This method sets up and starts an asynchronous streaming pull from a
        Google Cloud Pub/Sub subscription. It updates internal and Redis-based
        status markers, and handles both expected and unexpected termination
        of the pull process.

        Args:
            callback (Callable): A user-provided function that will be invoked
                for each received message.

        Behavior:
            - Initializes a Pub/Sub subscriber client and constructs the subscription path.
            - Starts streaming pull via `subscriber.subscribe`.
            - Blocks on `future.result()` until the stream is interrupted or stopped.
            - On successful start, sets the `_is_pulling` flag and updates Redis to RUNNING.
            - On `NotFound`, logs the error and deletes Redis status key.
            - On any other exception, logs the error and marks Redis status as FAILED.
            - In the `finally` block, always clears `_is_pulling` flag to ensure proper shutdown.
        """
        try:
            subscriber = GoogleClientFactory().create_subscriber_client()
            subscription_path = subscriber.subscription_path(
                self.project_id, self.subscription_id
            )

            wrapped_callback = self._wrap_callback_if_async(callback)
            self._streaming_pull_future = subscriber.subscribe(
                subscription_path, callback=wrapped_callback
            )
            logger.info(f"Subscription {self.subscription_id} listening started.")
            self._is_pulling.set()
            self._update_redis_pull_status(PullStatus.RUNNING)
            self._streaming_pull_future.result()

        except NotFound as nf_exc:
            logger.error(f"Subscription {self.subscription_id} not found: {nf_exc}")
            self._delete_redis_pull_status()

        except Exception as e:
            logger.error(f"Streaming pull for {self.subscription_id} interrupted: {e}")
            self._update_redis_pull_status(PullStatus.FAILED, error=str(e))

        finally:
            with self._lock:
                if self._is_pulling.is_set():
                    self._is_pulling.clear()
                    logger.debug(
                        f"_is_pulling flag cleared for {self.subscription_id} in _pull_target finally."
                    )

    def _check_subscription_exist(self):
        """
        Checks if the subscription configured for this Pub/Sub Puller instance
        exists within the specified Google Cloud project.
        """
        subscriber = GoogleClientFactory().create_subscriber_client()
        subscription_path = subscriber.subscription_path(
            self.project_id, self.subscription_id
        )
        try:
            subscriber.get_subscription(subscription=subscription_path)
            return True
        except NotFound:
            return False

    def start_pulling_messages(self, callback):
        """
        Starts asynchronous message pulling for this subscription.

        Behavior:
        - If already pulling (`_is_pulling` is set), it logs and exits.
        - If `_is_pulling` is not set but there is an active future, it attempts to stop the previous pull to avoid stale state.
        - Uses a background thread to subscribe to the stream and handle incoming messages asynchronously.
        - Handles graceful shutdown and failure reporting via Redis and internal state flags.

        Args:
            callback (Callable): A function that processes received Pub/Sub messages..
        """
        if callback is None:
            raise ValueError(
                "A message processing callback must be provided to start_pulling_messages."
            )

        is_exist = self._check_subscription_exist()
        if not is_exist:
            raise ValueError(
                "Resource not found. Please check the project ID and subscription ID."
            )

        with self._lock:
            if self._streaming_pull_future and not self._streaming_pull_future.done():
                if self._is_pulling.is_set():
                    logger.info(
                        f"Subscription {self.subscription_id} is already actively pulling messages."
                    )
                    return
                else:
                    logger.warning(
                        f"Detected stale streaming pull future for {self.subscription_id}, cancelling it..."
                    )
                    self.stop_pulling_messages()

        pull_thread = threading.Thread(
            target=self._pull_target, args=(callback,), daemon=True
        )
        pull_thread.start()

    def check_pulling_messages_status(self) -> PullStatusResponse:
        """
        Check the message pulling status for this subscription, verifying consistency between
        local state and Redis persistence.

        Returns:
            PullStatusResponse: An object containing:
                - subscription_id: The ID of this subscription
                - task_status: Current pull status code
                - message: Human-readable status message
                - timestamp: When the status was last updated (or None)

        Raises:
            ValueError: If Redis client is unavailable
            RuntimeError: If local and Redis states are inconsistent
            Exception: Any Redis operation errors
        """
        redis_client = RedisClientFactory().create_redis_client()
        if not redis_client:
            raise ValueError("Redis client not available. Cannot check pull status.")

        with self._lock:
            local_status_is_pulling = (
                self._is_pulling.is_set()
                and self._streaming_pull_future
                and (not self._streaming_pull_future.done())
            )
            try:
                redis_status_log = redis_client.hgetall(
                    PUBSUB_PULL_MESSAGES_STATUS_KEY.format(
                        subscription_id=self.subscription_id
                    )
                )
            except Exception as e:
                logger.error(
                    f"Failed to retrieve status from Redis for {self.subscription_id}: {e}"
                )
                raise

            if redis_status_log:
                task_status = redis_status_log.get("task_status")
                if local_status_is_pulling and task_status != PullStatus.RUNNING.code:
                    raise RuntimeError(
                        f"Status inconsistency detected for {self.subscription_id}: "
                        f"Local state indicates pulling, but Redis reports '{task_status}'."
                    )
                elif (
                    not local_status_is_pulling
                    and task_status == PullStatus.RUNNING.code
                ):
                    raise RuntimeError(
                        f"Status inconsistency detected for {self.subscription_id}: "
                        f"Local state indicates NOT pulling, but Redis reports '{task_status}'."
                    )

                message = redis_status_log.get("message")
                timestamp = redis_status_log.get("timestamp")
            else:
                if local_status_is_pulling:
                    raise RuntimeError(
                        f"Status inconsistency detected for {self.subscription_id}: "
                        f"Local state indicates pulling, but Redis has no status data."
                    )
                else:
                    status = PullStatus.NOT_STARTED
                    message = status.format_message(
                        subscription_id=self.subscription_id
                    )
                    task_status = status.code
                    timestamp = None

        response_obj = PullStatusResponse(
            subscription_id=self.subscription_id,
            task_status=task_status,
            message=message,
            timestamp=timestamp,
        )
        return response_obj

    def stop_pulling_messages(self):
        """
        Stops the ongoing asynchronous message pulling process.

        This method performs the following actions:
        - Acquires a lock to ensure thread-safe operation.
        - If there is no active pull task or the Future is already completed:
            - Logs the state and clears the `_is_pulling` flag if needed.
        - If a pull task is active:
            - Sends a cancellation signal to the Future.
            - Waits up to 3 seconds for graceful shutdown using `future.result(timeout=3)`.
            - Updates the Redis status based on the result of the cancellation:
                - If cancelled or completed successfully: status set to STOPPED.
                - If cancellation times out: status set to FAILED and raises TimeoutError.
                - If other errors occur: status set to FAILED and raises Exception.
            - Regardless of outcome, clears the `_is_pulling` flag in the `finally` block.

        Finally:
        - Calls and returns the result of `check_pulling_messages_status()` to verify the current status.

        Returns:
            PullStatusResponse: The current pulling status after attempting to stop.

        Raises:
            TimeoutError: If the cancellation does not complete within the timeout period.
            Exception: If an unexpected error occurs during shutdown.
        """
        with self._lock:
            future = self._streaming_pull_future
            if not future or future.done():
                if self._is_pulling.is_set():
                    logger.info(
                        f"No active pull Future found for subscription: {self.subscription_id}, but _is_pulling was set. Clearing flag."
                    )
                    self._is_pulling.clear()
                logger.info(
                    f"Subscription {self.subscription_id} is not actively pulling and no active future."
                )

            elif future and not future.done():
                logger.info(
                    f"Stopping async pull for subscription: {self.subscription_id}"
                )
                future.cancel()
                try:
                    future.result(timeout=3)
                    logger.info(
                        f"Subscription {self.subscription_id} listening cancelled and stream closed gracefully."
                    )
                    self._update_redis_pull_status(PullStatus.STOPPED)
                except concurrent.futures.CancelledError:
                    logger.info(
                        f"Subscription {self.subscription_id} Future was successfully cancelled."
                    )
                    self._update_redis_pull_status(PullStatus.STOPPED)
                except concurrent.futures.TimeoutError as e:
                    self._update_redis_pull_status(PullStatus.FAILED, error=str(e))
                    raise TimeoutError(
                        f"Cancellation for {self.subscription_id} timed out. Stream might not be fully closed yet."
                    )
                except Exception as e:
                    self._update_redis_pull_status(PullStatus.FAILED, error=str(e))
                    raise Exception(
                        f"Error during graceful shutdown for {self.subscription_id}: {e}"
                    )
                finally:
                    self._is_pulling.clear()
            return self.check_pulling_messages_status()
