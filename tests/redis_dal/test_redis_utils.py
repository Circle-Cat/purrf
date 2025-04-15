from unittest import TestCase, main
from unittest.mock import patch, Mock
from redis_dal.constants import (
    TYPE_CREATE,
    TYPE_UPDATE,
    TYPE_DELETE,
    MESSAGE,
    NAME,
    MESSAGE_SENDER,
    CREATE_TIME,
    MESSAGE_TEXT,
    MESSAGE_THREAD,
    MESSAGE_SPACE,
    MESSAGE_LAST_UPDATE_TIME,
    MESSAGE_DELETION_METADATA,
    MESSAGE_DELETION_TYPE,
    VALUE,
    MESSAGE_THREAD_ID,
    CHAT_INDEX_KEY_FORMAT,
    MESSAGE_ATTACHMENT,
)
from redis_dal.redis_utils import store_messages, StoredMessage
from datetime import datetime
import json

TEST_MESSAGE_NAME = "spaces/test_space/messages/test_message"
TEST_USER = {"name": "users/test_user", "type": "HUMAN"}
TEST_THREAD = {"name": "spaces/test_space/threads/test_thread"}
TEST_THREAD_ID = "test_thread"
TEST_SPACE = {"name": "spaces/test_space"}
TEST_SPACE_ID = "test_space"
TEST_ATTACHMENT = [
    {
        "name": f"{TEST_MESSAGE_NAME}/attachments/1",
        "contentName": "test_doc.pdf",
        "contentType": "application/pdf",
        "driveDataRef": {"driveFileId": "123456"},
        "source": "DRIVE_FILE",
    }
]
TEST_MESSAGE_TEXT = "Hello, World!"
TEST_TIME = datetime.utcnow().isoformat() + "Z"
TEST_SENDER_LDAP = "sender_name"
TEST_MOCK_CREATED_MESSAGE = {
    NAME: TEST_MESSAGE_NAME,
    MESSAGE_SENDER: TEST_USER,
    CREATE_TIME: TEST_TIME,
    MESSAGE_TEXT: TEST_MESSAGE_TEXT,
    MESSAGE_THREAD: TEST_THREAD,
    MESSAGE_SPACE: TEST_SPACE,
    MESSAGE_ATTACHMENT: TEST_ATTACHMENT,
}

TEST_MOCK_UPDATED_MESSAGE = {
    **TEST_MOCK_CREATED_MESSAGE,
    MESSAGE_LAST_UPDATE_TIME: TEST_TIME,
}

TEST_MOCK_DELETED_MESSAGE = {
    NAME: TEST_MESSAGE_NAME,
    CREATE_TIME: TEST_TIME,
}


def create_stored_message(texts, deleted=False):
    return json.dumps(
        StoredMessage(
            sender=TEST_SENDER_LDAP,
            threadId=TEST_THREAD_ID,
            text=texts,
            deleted=deleted,
            attachment=TEST_ATTACHMENT,
        ).__dict__
    )


TEST_STORED_CREATED_MESSAGE = create_stored_message([
    {VALUE: TEST_MESSAGE_TEXT, CREATE_TIME: TEST_TIME}
])

TEST_STORED_UPDATED_MESSAGE = create_stored_message([
    {VALUE: TEST_MESSAGE_TEXT, CREATE_TIME: TEST_TIME},
    {VALUE: TEST_MESSAGE_TEXT, CREATE_TIME: TEST_TIME},
])

TEST_STORED_DELETED_MESSAGE = create_stored_message(
    [{VALUE: TEST_MESSAGE_TEXT, CREATE_TIME: TEST_TIME}], deleted=True
)


class TestStoreMessages(TestCase):
    def setUp(self):
        """Setup mock Redis client before each test"""
        self.patcher = patch(
            "redis_dal.redis_client_factory.RedisClientFactory.create_redis_client"
        )
        self.mock_create_redis_client = self.patcher.start()
        self.mock_redis_client = Mock()
        self.mock_create_redis_client.return_value = self.mock_redis_client

    def tearDown(self):
        """Stop patching after each test"""
        self.patcher.stop()

    def test_store_created_messages_success(self):
        store_messages(TEST_SENDER_LDAP, TEST_MOCK_CREATED_MESSAGE, TYPE_CREATE)

        index_redis_key = CHAT_INDEX_KEY_FORMAT.format(
            space_id=TEST_SPACE_ID, sender_ldap=TEST_SENDER_LDAP
        )
        score = datetime.fromisoformat(TEST_TIME).timestamp()
        redis_member = str({NAME: TEST_MESSAGE_NAME})

        self.mock_redis_client.zadd.assert_called_once_with(
            index_redis_key, {redis_member: score}
        )
        self.mock_redis_client.set.assert_called_once_with(
            TEST_MESSAGE_NAME, TEST_STORED_CREATED_MESSAGE
        )

    def test_store_updated_messages_success(self):
        self.mock_redis_client.get.return_value = TEST_STORED_CREATED_MESSAGE

        store_messages(TEST_SENDER_LDAP, TEST_MOCK_UPDATED_MESSAGE, TYPE_UPDATE)

        self.mock_redis_client.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis_client.set.assert_called_once_with(
            TEST_MESSAGE_NAME, TEST_STORED_UPDATED_MESSAGE
        )

    def test_store_deleted_messages_success(self):
        self.mock_redis_client.get.return_value = TEST_STORED_CREATED_MESSAGE

        store_messages(TEST_SENDER_LDAP, TEST_MOCK_DELETED_MESSAGE, TYPE_DELETE)

        index_redis_key = CHAT_INDEX_KEY_FORMAT.format(
            space_id=TEST_SPACE_ID, sender_ldap=TEST_SENDER_LDAP
        )
        score = datetime.fromisoformat(TEST_TIME).timestamp()
        redis_member = str({NAME: TEST_MESSAGE_NAME})

        self.mock_redis_client.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis_client.set.assert_called_once_with(
            TEST_MESSAGE_NAME, TEST_STORED_DELETED_MESSAGE
        )
        self.mock_redis_client.zrem.assert_called_once_with(
            index_redis_key, redis_member
        )

    def test_store_updated_message_does_not_exist(self):
        self.mock_redis_client.get.return_value = None

        store_messages(TEST_SENDER_LDAP, TEST_MOCK_UPDATED_MESSAGE, TYPE_UPDATE)

        self.mock_redis_client.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis_client.set.assert_not_called()

    def test_store_deleted_message_does_not_exist(self):
        self.mock_redis_client.get.return_value = None

        store_messages(TEST_SENDER_LDAP, TEST_MOCK_DELETED_MESSAGE, TYPE_DELETE)

        self.mock_redis_client.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis_client.zrem.assert_not_called()
        self.mock_redis_client.set.assert_not_called()

    def test_store_created_message_invalid_format(self):
        store_messages(TEST_SENDER_LDAP, "{invalid_json}", TYPE_CREATE)

        self.mock_redis_client.zadd.assert_not_called()
        self.mock_redis_client.set.assert_not_called()


if __name__ == "__main__":
    main()
