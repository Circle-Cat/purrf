from src.common.redis_client import RedisClientFactory
from src.common.constants import PullStatus, PUBSUB_PULL_MESSAGES_STATUS_KEY
from src.common.logger import get_logger
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
import time


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
                except concurrent.futures.CancelledError as e:
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
