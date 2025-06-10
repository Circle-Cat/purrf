from src.common.redis_client import RedisClientFactory
from src.common.constants import PullStatus, PUBSUB_PULL_MESSAGES_STATUS_KEY
from src.common.logger import get_logger
from dataclasses import dataclass
import concurrent.futures
import threading


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
