from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError
import os
from tools.log.logger import setup_logger
import logging
from redis_dal.constants import (
    REDIS_HOST_PORT_ERROR_MSG,
    REDIS_CLIENT_CREATED_MSG,
    HOST,
    PASSWORD,
    PORT,
)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
)

setup_logger()


class RedisClientError(Exception):
    """Exception raised when creating the Redis client fails."""


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
        client = Redis(host=host, port=port, password=password, ssl=True)
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
        if self._redis_client is None:
            redis_host = os.environ.get(HOST)
            redis_port = os.environ.get(PORT)
            redis_password = os.environ.get(PASSWORD)

            if not redis_host or not redis_port:
                logging.error("Redis host or port environment variables are missing.")
                raise ValueError(REDIS_HOST_PORT_ERROR_MSG)

            try:
                self._redis_client = self._connect_to_redis(
                    host=redis_host,
                    port=int(redis_port),
                    password=redis_password,
                )
                logging.info(
                    REDIS_CLIENT_CREATED_MSG.format(redis_client=self._redis_client)
                )
            except (RedisConnectionError, TimeoutError) as e:
                logging.error(f"Failed to connect to Redis server after retries: {e}")
                raise RedisClientError("Failed to create Redis client.") from e
            except Exception as e:
                logging.error(f"Unexpected error during Redis client creation: {e}")
                raise

        return self._redis_client
