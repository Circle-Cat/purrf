from unittest import TestCase, main
from unittest.mock import patch, Mock
from src.utils.google_chat_message_store import store_messages, StoredMessage
from datetime import datetime
import json
from src.common.constants import (
    CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY,
    DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY,
    GoogleChatEventType,
)

TEST_MESSAGE_ID = "test_message"
TEST_MESSAGE_NAME = f"spaces/test_space/messages/{TEST_MESSAGE_ID}"
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
    "name": TEST_MESSAGE_NAME,
    "sender": TEST_USER,
    "createTime": TEST_TIME,
    "text": TEST_MESSAGE_TEXT,
    "thread": TEST_THREAD,
    "space": TEST_SPACE,
    "attachment": TEST_ATTACHMENT,
}

TEST_MOCK_UPDATED_MESSAGE = {
    **TEST_MOCK_CREATED_MESSAGE,
    "lastUpdateTime": TEST_TIME,
}

TEST_MOCK_DELETED_MESSAGE = {
    "name": TEST_MESSAGE_NAME,
    "createTime": TEST_TIME,
}


def create_stored_message(texts, deleted=False):
    return json.dumps(
        StoredMessage(
            sender=TEST_SENDER_LDAP,
            threadId=TEST_THREAD_ID,
            text=texts,
            is_deleted=deleted,
            attachment=TEST_ATTACHMENT,
        ).__dict__
    )


TEST_STORED_CREATED_MESSAGE = create_stored_message([
    {"value": TEST_MESSAGE_TEXT, "createTime": TEST_TIME}
])

TEST_STORED_UPDATED_MESSAGE = create_stored_message([
    {"value": TEST_MESSAGE_TEXT, "createTime": TEST_TIME},
    {"value": TEST_MESSAGE_TEXT, "createTime": TEST_TIME},
])

TEST_STORED_INVALIDED_UPDATED_MESSAGE = create_stored_message(None)

TEST_STORED_DELETED_MESSAGE = create_stored_message(
    [{"value": TEST_MESSAGE_TEXT, "createTime": TEST_TIME}], deleted=True
)

TEST_INDEX_REDIS_KEY = CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
    space_id=TEST_SPACE_ID, sender_ldap=TEST_SENDER_LDAP
)
TEST_DELETED_INDEX_REDIS_KEY = DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
    space_id=TEST_SPACE_ID, sender_ldap=TEST_SENDER_LDAP
)

REDIS_MEMEBER = TEST_MESSAGE_ID
TEST_SCORE = datetime.fromisoformat(TEST_TIME).timestamp()


class TestStoreMessages(TestCase):
    def setUp(self):
        """Setup mock Redis client before each test"""
        self.patcher = patch(
            "src.utils.google_chat_message_store.RedisClientFactory.create_redis_client"
        )
        self.mock_create_redis_client = self.patcher.start()
        self.mock_redis_client = Mock()
        self.mock_create_redis_client.return_value = self.mock_redis_client
        self.mock_pipeline = Mock()
        self.mock_redis_client.pipeline.return_value = self.mock_pipeline

    def tearDown(self):
        """Stop patching after each test"""
        self.patcher.stop()

    def test_store_created_messages_success(self):
        store_messages(
            TEST_SENDER_LDAP,
            TEST_MOCK_CREATED_MESSAGE,
            GoogleChatEventType.CREATED.value,
        )

        self.mock_create_redis_client.assert_called_once()
        self.mock_redis_client.pipeline.assert_called_once()
        self.mock_pipeline.zadd.assert_called_once_with(
            TEST_INDEX_REDIS_KEY, {REDIS_MEMEBER: TEST_SCORE}
        )
        self.mock_pipeline.set.assert_called_once_with(
            TEST_MESSAGE_NAME, TEST_STORED_CREATED_MESSAGE
        )
        self.mock_pipeline.execute.assert_called_once()

    def test_store_updated_messages_success(self):
        self.mock_redis_client.get.return_value = TEST_STORED_CREATED_MESSAGE

        store_messages(
            TEST_SENDER_LDAP,
            TEST_MOCK_UPDATED_MESSAGE,
            GoogleChatEventType.UPDATED.value,
        )

        self.mock_redis_client.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis_client.set.assert_called_once_with(
            TEST_MESSAGE_NAME, TEST_STORED_UPDATED_MESSAGE
        )

    def test_store_deleted_messages_success(self):
        self.mock_redis_client.get.return_value = TEST_STORED_CREATED_MESSAGE
        self.mock_redis_client.zscore.return_value = TEST_SCORE

        store_messages(
            TEST_SENDER_LDAP,
            TEST_MOCK_DELETED_MESSAGE,
            GoogleChatEventType.DELETED.value,
        )

        self.mock_redis_client.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis_client.zscore.assert_called_once_with(
            TEST_INDEX_REDIS_KEY, REDIS_MEMEBER
        )
        self.mock_pipeline.set.assert_called_once_with(
            TEST_MESSAGE_NAME, TEST_STORED_DELETED_MESSAGE
        )
        self.mock_pipeline.zrem.assert_called_once_with(
            TEST_INDEX_REDIS_KEY, REDIS_MEMEBER
        )

        self.mock_pipeline.zadd.assert_called_once_with(
            TEST_DELETED_INDEX_REDIS_KEY, {REDIS_MEMEBER: TEST_SCORE}
        )
        self.mock_pipeline.execute.assert_called_once()

    def test_store_updated_message_does_not_exist(self):
        self.mock_redis_client.get.return_value = None

        with self.assertRaises(ValueError):
            store_messages(
                TEST_SENDER_LDAP,
                TEST_MOCK_UPDATED_MESSAGE,
                GoogleChatEventType.UPDATED.value,
            )

        self.mock_redis_client.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis_client.set.assert_not_called()

    def test_store_updated_message_with_data_inconsistent(self):
        self.mock_redis_client.get.return_value = TEST_STORED_INVALIDED_UPDATED_MESSAGE

        with self.assertRaises(TypeError):
            store_messages(
                TEST_SENDER_LDAP,
                TEST_MOCK_UPDATED_MESSAGE,
                GoogleChatEventType.UPDATED.value,
            )

        self.mock_redis_client.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis_client.set.assert_not_called()

    def test_store_deleted_message_does_not_exist(self):
        self.mock_redis_client.get.return_value = None

        with self.assertRaises(ValueError):
            store_messages(
                TEST_SENDER_LDAP,
                TEST_MOCK_DELETED_MESSAGE,
                GoogleChatEventType.DELETED.value,
            )

        self.mock_redis_client.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_pipeline.zrem.assert_not_called()
        self.mock_pipeline.set.assert_not_called()
        self.mock_pipeline.execute.assert_not_called()

    def test_store_created_message_invalid_format(self):
        with self.assertRaises(AttributeError):
            store_messages(
                TEST_SENDER_LDAP, "{invalid_json}", GoogleChatEventType.CREATED.value
            )

        self.mock_pipeline.zadd.assert_not_called()
        self.mock_pipeline.set.assert_not_called()
        self.mock_pipeline.execute.assert_not_called()


if __name__ == "__main__":
    main()
