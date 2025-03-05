import unittest
from unittest.mock import patch, Mock
from redis_dal.constants import (
    REDIS_KEY_FORMAT,
    REDIS_MESSAGE_STORED_DEBUG_MSG,
)
from io import StringIO
import logging
from tools.log.logger import setup_logger
from redis_dal.redis_utils import store_messages
from datetime import datetime


class TestStoreMessages(unittest.TestCase):
    def setUp(self):
        self.log_capture_string = StringIO()
        ch = logging.StreamHandler(self.log_capture_string)
        setup_logger()
        root_logger = logging.getLogger()
        ch.setFormatter(root_logger.handlers[0].formatter)
        logging.getLogger().addHandler(ch)
        logging.getLogger().setLevel(logging.DEBUG)

    def tearDown(self):
        logging.getLogger().handlers = []

    @patch("redis_dal.redis_client_factory.RedisClientFactory.create_redis_client")
    def test_store_messages_success(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_create_redis_client.return_value = mock_redis_client

        sender_ldap = "test_user"
        message = {
            "createTime": "2023-10-27T10:00:00Z",
            "space": {"name": "spaces/dasdaeeurw"},
            "text": "Hello, world!",
        }
        message_type = "create"

        store_messages(sender_ldap, message, message_type)

        space_id = message["space"]["name"].split("/")[1]
        redis_key = REDIS_KEY_FORMAT.format(space_id=space_id, sender_ldap=sender_ldap)
        score = datetime.fromisoformat(message["createTime"]).timestamp()
        redis_member = str({"message": message, "type": message_type})

        mock_redis_client.zadd.assert_called_once_with(redis_key, {redis_member: score})

        log_output = self.log_capture_string.getvalue()
        self.assertIn(
            REDIS_MESSAGE_STORED_DEBUG_MSG.format(redis_key=redis_key, score=score),
            log_output,
        )

    def test_store_messages_invalid_create_time(self):
        sender_ldap = "test_user"
        message = {"createTime": "invalid_time", "space": {"name": "MySpace"}}
        message_type = "create"

        with self.assertRaises(ValueError):
            store_messages(sender_ldap, message, message_type)


if __name__ == "__main__":
    unittest.main()
