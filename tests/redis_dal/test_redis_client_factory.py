import unittest
from unittest.mock import patch
import os
from redis_dal.redis_client_factory import RedisClientFactory
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
        logging.getLogger().addHandler(ch)

        os.environ.pop(HOST, None)
        os.environ.pop(PORT, None)
        os.environ.pop(PASSWORD, None)
        RedisClientFactory._instance = None
        RedisClientFactory._redis_client = None

    def tearDown(self):
        logging.getLogger().handlers = []

    @patch("redis_dal.redis_client_factory.Redis")
    def test_create_redis_client_success(self, mock_redis):
        os.environ[HOST] = TEST_HOST
        os.environ[PORT] = TEST_PORT
        os.environ[PASSWORD] = TEST_PASSWORD

        factory = RedisClientFactory()
        client = factory.create_redis_client()

        mock_redis.assert_called_once_with(
            host=TEST_HOST, port=TEST_PORT, password=TEST_PASSWORD, ssl=True
        )
        log_output = self.log_capture_string.getvalue()
        self.assertIn(REDIS_CLIENT_CREATED_MSG.format(redis_client=client), log_output)

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

    @patch("redis_dal.redis_client_factory.Redis")
    def test_singleton_behavior(self, mock_redis):
        os.environ[HOST] = TEST_HOST
        os.environ[PORT] = TEST_PORT
        os.environ[PASSWORD] = TEST_PASSWORD

        factory = RedisClientFactory()
        client1 = factory.create_redis_client()
        client2 = factory.create_redis_client()

        self.assertIs(client1, client2)
        mock_redis.assert_called_once()

    @patch(
        "redis_dal.redis_client_factory.Redis",
        side_effect=Exception(TEST_EXCEPTION_MSG),
    )
    def test_redis_client_creation_failure(self, mock_redis):
        os.environ[HOST] = TEST_HOST
        os.environ[PORT] = TEST_PORT
        os.environ[PASSWORD] = TEST_PASSWORD

        factory = RedisClientFactory()
        with self.assertRaises(Exception) as cm:
            factory.create_redis_client()
        self.assertEqual(str(cm.exception), TEST_EXCEPTION_MSG)


if __name__ == "__main__":
    unittest.main()
