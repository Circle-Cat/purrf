from unittest import TestCase, main
from unittest.mock import patch, Mock
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError
from src.common.redis_client import RedisClientFactory, RedisClientError
from src.common.environment_constants import (
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)

from tenacity import RetryError
import os

TEST_REDIS_HOST = "localhost"
TEST_REDIS_PORT = "6379"
TEST_REDIS_PASSWORD = "password"


class TestRedisClientFactory(TestCase):
    def setUp(self):
        RedisClientFactory._instance = None
        RedisClientFactory._redis_client = None

    @patch("src.common.redis_client.RedisClientFactory._connect_to_redis")
    @patch.dict(
        os.environ,
        {
            REDIS_HOST: TEST_REDIS_HOST,
            REDIS_PORT: TEST_REDIS_PORT,
            REDIS_PASSWORD: TEST_REDIS_PASSWORD,
        },
    )
    def test_create_redis_client_success(self, mock_connect):
        mock_client = Mock()
        mock_connect.return_value = mock_client

        factory = RedisClientFactory()
        client = factory.create_redis_client()

        mock_connect.assert_called_once_with(
            host=TEST_REDIS_HOST,
            port=int(TEST_REDIS_PORT),
            password=TEST_REDIS_PASSWORD,
        )
        self.assertIsNotNone(client)

    @patch.dict(os.environ, {REDIS_PASSWORD: TEST_REDIS_PASSWORD})
    def test_create_redis_client_missing_host(self):
        factory = RedisClientFactory()

        with self.assertRaises(ValueError):
            factory.create_redis_client()

    @patch.dict(os.environ, {REDIS_HOST: TEST_REDIS_HOST})
    def test_create_redis_client_missing_port(self):
        factory = RedisClientFactory()

        with self.assertRaises(ValueError):
            factory.create_redis_client()

    @patch("src.common.redis_client.RedisClientFactory._connect_to_redis")
    @patch.dict(
        os.environ,
        {
            REDIS_HOST: TEST_REDIS_HOST,
            REDIS_PORT: TEST_REDIS_PORT,
            REDIS_PASSWORD: TEST_REDIS_PASSWORD,
        },
    )
    def test_singleton_behavior(self, mock_connect):
        mock_client = Mock()
        mock_connect.return_value = mock_client

        factory = RedisClientFactory()
        client1 = factory.create_redis_client()
        client2 = factory.create_redis_client()

        self.assertIs(client1, client2)
        mock_connect.assert_called_once()

    @patch("src.common.redis_client.Redis")
    def test_connect_to_redis_success(self, mock_redis):
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        factory = RedisClientFactory()
        client = factory._connect_to_redis(
            TEST_REDIS_HOST, int(TEST_REDIS_PORT), TEST_REDIS_PASSWORD
        )

        mock_redis.assert_called_once_with(
            host=TEST_REDIS_HOST,
            port=int(TEST_REDIS_PORT),
            password=TEST_REDIS_PASSWORD,
            ssl=True,
        )
        mock_client.ping.assert_called_once()
        self.assertEqual(client, mock_client)

    @patch("src.common.redis_client.Redis")
    def test_connect_to_redis_retry_on_failure(self, mock_redis):
        mock_client = Mock()
        mock_client.ping.return_value = True

        mock_redis.side_effect = [
            RedisConnectionError(),
            mock_client,
        ]

        factory = RedisClientFactory()
        client = factory._connect_to_redis(
            TEST_REDIS_HOST, int(TEST_REDIS_PORT), TEST_REDIS_PASSWORD
        )

        self.assertEqual(mock_redis.call_count, 2)
        mock_client.ping.assert_called_once()
        self.assertEqual(client, mock_client)

    @patch("src.common.redis_client.Redis")
    def test_connect_to_redis_max_retries_exceeded(self, mock_redis):
        mock_redis.side_effect = RedisConnectionError()

        factory = RedisClientFactory()

        with self.assertRaises(RetryError):
            factory._connect_to_redis(
                TEST_REDIS_HOST, int(TEST_REDIS_PORT), TEST_REDIS_PASSWORD
            )

        self.assertEqual(mock_redis.call_count, 3)


if __name__ == "__main__":
    main()
