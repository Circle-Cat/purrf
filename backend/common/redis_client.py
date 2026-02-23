from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError
from backend.common.environment_constants import (
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)
from backend.common.logger import get_logger
import os

logger = get_logger()


class RedisClientError(Exception):
    """Exception raised when creating the Redis client fails."""


class RedisClient:
    """
    A Redis client factory that creates and caches a Redis client.

    This class allows dependency injection of Redis connection parameters, logger,
    and retry utility. It retries connection attempts for transient errors
    using the provided RetryUtils instance.

    Attributes:
        _redis_client (Redis | None): Cached Redis client instance.
    """

    def __init__(
        self,
        logger,
        retry_utils,
    ):
        """
        Initialize the Redis client factory.

        Args:
            logger: Logger instance for logging.
            retry_utils: RetryUtils instance providing retry logic.

        Raises:
            ValueError: If any Redis connection parameter is missing.
        """
        self.logger = logger
        self.retry_utils = retry_utils
        self._redis_client = self.create_redis_client()

    def _connect_to_redis(self) -> Redis:
        """
        Attempt to create a Redis client and verify connectivity.

        Returns:
            Redis: Connected Redis client.

        Raises:
            RedisConnectionError: If a connection-related error occurs.
            TimeoutError: If a timeout occurs during connection.
        """
        client = Redis(
            host=os.environ.get(REDIS_HOST),
            port=os.environ.get(REDIS_PORT),
            password=os.environ.get(REDIS_PASSWORD),
            ssl=True,
            decode_responses=True,
        )
        client.ping()
        return client

    def create_redis_client(self) -> Redis:
        """
        Create and return the Redis client instance.

        Retries transient connection errors using the injected RetryUtils instance.

        Returns:
            Redis: Connected Redis client.

        Raises:
            RedisClientError: If connection fails after retries.
            Exception: For any unexpected errors during client creation.
        """
        try:
            redis_client = self.retry_utils.get_retry_on_transient(
                self._connect_to_redis
            )
            self.logger.info("Created Redis client successfully.")
        except (RedisConnectionError, TimeoutError) as e:
            self.logger.error(
                f"Failed to connect to Redis server {self._redis_host}:{self._redis_port} after retries: {e}"
            )
            raise RedisClientError("Failed to create Redis client.")
        except Exception as e:
            self.logger.error(f"Unexpected error during Redis client creation: {e}")
            raise

        return redis_client

    def get_redis_client(self) -> Redis:
        """
        Return the cached Redis client instance (now always initialized).

        Returns:
            Redis: Connected Redis client.
        """
        return self._redis_client
