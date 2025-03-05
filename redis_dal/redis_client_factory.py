from redis import Redis
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

setup_logger()


class RedisClientFactory:
    """
    A singleton factory class for creating and managing a Redis client.

    This class ensures that only one Redis client instance is created and shared across the application.
    It retrieves Redis connection parameters from environment variables and handles client creation
    and error handling.

    Attributes:
        _instance (RedisClientFactory): The singleton instance of the factory.
        _redis_client (redis.Redis): The created Redis client instance.

    Methods:
        __new__(cls, *args, **kwargs): Creates or returns the singleton instance of the factory.
        create_redis_client(self): Creates and returns a Redis client, or returns the existing one.

    Raises:
        ValueError: If Redis host or port are not set in environment variables.
        redis.exceptions.RedisError: If an error occurs during Redis client creation.
        Exception: For any other unexpected errors during client creation.
    """

    _instance = None
    _redis_client = None

    def __new__(cls, *args, **kwargs):
        """
        Creates or returns the singleton instance of the RedisClientFactory.

        Args:
            cls (type): The class itself.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            RedisClientFactory: The singleton instance.
        """

        if not cls._instance:
            cls._instance = super(RedisClientFactory, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def create_redis_client(self):
        """
        Creates and returns a Redis client, or returns the existing one.

        Retrieves Redis connection parameters from environment variables and creates a Redis client.
        If a client already exists, it returns the existing client instance.

        Returns:
            redis.Redis: The Redis client instance.

        Raises:
            ValueError: If Redis host or port are not set in environment variables.
        """

        if self._redis_client is None:
            redis_host = os.environ.get(HOST)
            redis_port = os.environ.get(PORT)
            redis_password = os.environ.get(PASSWORD)

            if not redis_host or not redis_port:
                raise ValueError(REDIS_HOST_PORT_ERROR_MSG)

            self._redis_client = Redis(
                host=redis_host, port=redis_port, password=redis_password, ssl=True
            )
            logging.info(
                REDIS_CLIENT_CREATED_MSG.format(redis_client=self._redis_client)
            )

        return self._redis_client
