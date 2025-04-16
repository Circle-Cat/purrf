import unittest
from unittest.mock import patch, Mock
import os
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError
from redis_dal.redis_client_factory import RedisClientFactory, RedisClientError
from redis_dal.constants import (
    REDIS_HOST_PORT_ERROR_MSG,
    REDIS_CLIENT_CREATED_MSG,
    HOST,
    PASSWORD,
    PORT,
)
from io import StringIO
import logging
from tools.log.logger import setup_logger
from tenacity import RetryError

TEST_HOST = "localhost"
TEST_PORT = "6379"
TEST_PASSWORD = "password"
TEST_EXCEPTION_MSG = "Connection error"


class TestRedisClientFactory(unittest.TestCase):
    def setUp(self):
        self.log_capture_string = StringIO()
        ch = logging.StreamHandler(self.log_capture_string)
        setup_logger()
        root_logger = logging.getLogger()
        ch.setFormatter(root_logger.handlers[0].formatter)
        root_logger.addHandler(ch)

        os.environ.pop(HOST, None)
        os.environ.pop(PORT, None)
        os.environ.pop(PASSWORD, None)
        RedisClientFactory._instance = None
        RedisClientFactory._redis_client = None

    def tearDown(self):
        logging.getLogger().handlers = []

    @patch("redis_dal.redis_client_factory.RedisClientFactory._connect_to_redis")
    def test_create_redis_client_success(self, mock_connect):
        mock_client = Mock()
        mock_connect.return_value = mock_client

        os.environ[HOST] = TEST_HOST
        os.environ[PORT] = TEST_PORT
        os.environ[PASSWORD] = TEST_PASSWORD

        factory = RedisClientFactory()
        client = factory.create_redis_client()

        mock_connect.assert_called_once_with(
            host=TEST_HOST, port=int(TEST_PORT), password=TEST_PASSWORD
        )
        self.assertIsNotNone(client)

    def test_create_redis_client_missing_host(self):
        os.environ[PASSWORD] = TEST_PASSWORD
        factory = RedisClientFactory()

        with self.assertRaises(ValueError) as cm:
            factory.create_redis_client()
        self.assertEqual(str(cm.exception), REDIS_HOST_PORT_ERROR_MSG)

    def test_create_redis_client_missing_port(self):
        os.environ[HOST] = TEST_HOST
        factory = RedisClientFactory()

        with self.assertRaises(ValueError) as cm:
            factory.create_redis_client()
        self.assertEqual(str(cm.exception), REDIS_HOST_PORT_ERROR_MSG)

    @patch("redis_dal.redis_client_factory.RedisClientFactory._connect_to_redis")
    def test_singleton_behavior(self, mock_connect):
        mock_client = Mock()
        mock_connect.return_value = mock_client

        os.environ[HOST] = TEST_HOST
        os.environ[PORT] = TEST_PORT
        os.environ[PASSWORD] = TEST_PASSWORD

        factory = RedisClientFactory()
        client1 = factory.create_redis_client()
        client2 = factory.create_redis_client()

        self.assertIs(client1, client2)
        mock_connect.assert_called_once()

    @patch("redis_dal.redis_client_factory.Redis")
    def test_connect_to_redis_success(self, mock_redis):
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        factory = RedisClientFactory()
        client = factory._connect_to_redis(TEST_HOST, int(TEST_PORT), TEST_PASSWORD)

        mock_redis.assert_called_once_with(
            host=TEST_HOST, port=int(TEST_PORT), password=TEST_PASSWORD, ssl=True
        )
        mock_client.ping.assert_called_once()
        self.assertEqual(client, mock_client)

    @patch("redis_dal.redis_client_factory.Redis")
    def test_connect_to_redis_retry_on_failure(self, mock_redis):
        mock_client = Mock()
        mock_client.ping.return_value = True

        mock_redis.side_effect = [
            RedisConnectionError(TEST_EXCEPTION_MSG),
            mock_client,
        ]

        factory = RedisClientFactory()
        client = factory._connect_to_redis(TEST_HOST, int(TEST_PORT), TEST_PASSWORD)

        self.assertEqual(mock_redis.call_count, 2)
        mock_client.ping.assert_called_once()
        self.assertEqual(client, mock_client)

    @patch("redis_dal.redis_client_factory.Redis")
    def test_connect_to_redis_max_retries_exceeded(self, mock_redis):
        mock_redis.side_effect = RedisConnectionError(TEST_EXCEPTION_MSG)

        factory = RedisClientFactory()

        with self.assertRaises(RetryError):
            factory._connect_to_redis(TEST_HOST, int(TEST_PORT), TEST_PASSWORD)

        self.assertEqual(mock_redis.call_count, 3)


if __name__ == "__main__":
    unittest.main()
