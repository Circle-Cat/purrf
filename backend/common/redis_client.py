from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError
from backend.common.environment_constants import (
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
)
from backend.common.logger import get_logger
import os

logger = get_logger()


class RedisClientError(Exception):
    """Exception raised when creating the Redis client fails."""


# TODO: Delete this class after all references and related imports are removed.
class RedisClientFactory:
    """
    A singleton factory class for creating and managing a Redis client.

    This class ensures that only one Redis client instance is created and shared across the application.
    It retrieves Redis connection parameters from environment variables and handles client creation
    and error handling with automatic retries on transient connection errors.

    Attributes:
        _instance (RedisClientFactory): The singleton instance of the factory.
        _redis_client (redis.Redis): The created Redis client instance.

    Methods:
        __new__(cls, *args, **kwargs): Creates or returns the singleton instance of the factory.
        _connect_to_redis(self, host: str, port: int, password: str) -> Redis:
            Internal method to create and connect a Redis client with retry logic.
        create_redis_client(self) -> Redis:
            Creates and returns a Redis client, or returns the existing one.

    Raises:
        ValueError: If Redis host or port are not set in environment variables.
        RedisClientError: If an error occurs during Redis client creation after retries.
        Exception: For any other unexpected errors during client creation.
    """

    _instance = None
    _redis_client = None

    def __new__(cls, *args, **kwargs):
        """
        Create or return the singleton instance of RedisClientFactory.
        """
        if not cls._instance:
            cls._instance = super(RedisClientFactory, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((RedisConnectionError, TimeoutError)),
    )
    def _connect_to_redis(self, host: str, port: int, password: str) -> Redis:
        """
        Internal method to create a Redis client with retry on connection errors.

        Args:
            host (str): Redis server host.
            port (int): Redis server port.
            password (str): Redis server password.

        Returns:
            Redis: The connected Redis client.

        Raises:
            RedisConnectionError: If a connection-related error occurs.
            TimeoutError: If a timeout occurs during connection.
        """
        client = Redis(
            host=host, port=port, password=password, ssl=True, decode_responses=True
        )
        client.ping()
        return client

    def create_redis_client(self) -> Redis:
        """
        Create and return a Redis client instance, or return the existing one.

        This method retrieves connection parameters from environment variables and attempts
        to establish a connection to the Redis server. If a Redis connection error or timeout
        occurs, it will retry automatically. If all retries fail, it raises RedisClientError.

        Returns:
            Redis: The Redis client instance.

        Raises:
            ValueError: If Redis host or port are not set in environment variables.
            RedisClientError: If the Redis client fails to connect after retries.
            Exception: If an unexpected error occurs during client creation.
        """
        if self._redis_client:
            return self._redis_client

        redis_host = os.environ.get(REDIS_HOST)
        redis_port = os.environ.get(REDIS_PORT)
        redis_password = os.environ.get(REDIS_PASSWORD)

        if not redis_host:
            logger.error(
                f"Initialize Redis client failed: environment variable {REDIS_HOST} is not set."
            )
            raise ValueError(f"Please set environment variable: {REDIS_HOST}.")
        if not redis_port:
            logger.error(
                f"Initialize Redis client failed: environment variable {REDIS_PORT} is not set."
            )
            raise ValueError(f"Please set environment variable: {REDIS_PORT}.")
        if not redis_password:
            logger.error(
                f"Initialize Redis client failed: environment variable {REDIS_PASSWORD} is not set."
            )
            raise ValueError(f"Please set environment variable: {REDIS_PASSWORD}.")
        try:
            self._redis_client = self._connect_to_redis(
                host=redis_host,
                port=int(redis_port),
                password=redis_password,
            )
            logger.info("Created Redis client successfully.")
        except (RedisConnectionError, TimeoutError) as e:
            logger.error(
                f"Failed to connect to Redis server {redis_host}:{redis_port} after retries: {e}"
            )
            raise RedisClientError("Failed to create Redis client.")
        except Exception as e:
            logger.error(f"Unexpected error during Redis client creation: {e}")
            raise

        return self._redis_client


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
