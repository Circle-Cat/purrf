import json
from unittest import TestCase, main
from unittest.mock import Mock
from datetime import datetime

from backend.utils.google_chat_message_utils import (
    GoogleChatMessagesUtils,
    StoredGoogleChatMessage,
    TextContent,
)
from backend.common.constants import (
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

TEST_MOCK_LDAP_MAPPING = {TEST_USER["name"]: TEST_SENDER_LDAP}


TEST_MOCK_CREATED_MESSAGE_PAYLOAD = {
    "message": {
        "name": TEST_MESSAGE_NAME,
        "sender": TEST_USER,
        "createTime": TEST_TIME,
        "text": TEST_MESSAGE_TEXT,
        "thread": TEST_THREAD,
        "space": TEST_SPACE,
        "attachment": TEST_ATTACHMENT,
    }
}

TEST_MOCK_UPDATED_MESSAGE_PAYLOAD = {
    "message": {
        **TEST_MOCK_CREATED_MESSAGE_PAYLOAD["message"],
        "lastUpdateTime": TEST_TIME,
    }
}

TEST_MOCK_DELETED_MESSAGE_PAYLOAD = {
    "message": {
        "name": TEST_MESSAGE_NAME,
        "createTime": TEST_TIME,
    }
}


def create_stored_message_json(texts, deleted=False):
    obj = StoredGoogleChatMessage(
        sender=TEST_SENDER_LDAP,
        thread_id=TEST_THREAD_ID,
        text=[TextContent(**t) for t in (texts or [])],
        is_deleted=deleted,
        attachment=TEST_ATTACHMENT,
    ).to_dict()
    return json.dumps(obj)


TEST_STORED_CREATED_MESSAGE = create_stored_message_json([
    {"value": TEST_MESSAGE_TEXT, "create_time": TEST_TIME}
])

TEST_STORED_UPDATED_MESSAGE_PRE_UPDATE = create_stored_message_json([
    {"value": TEST_MESSAGE_TEXT, "create_time": TEST_TIME}
])

TEST_STORED_UPDATED_MESSAGE_POST_UPDATE = create_stored_message_json([
    {"value": TEST_MESSAGE_TEXT, "create_time": TEST_TIME},
    {"value": TEST_MESSAGE_TEXT, "create_time": TEST_TIME},
])

TEST_STORED_INVALID_UPDATED_MESSAGE = json.dumps({
    "sender": TEST_SENDER_LDAP,
    "thread_id": TEST_THREAD_ID,
    "text": None,
    "is_deleted": False,
    "attachment": TEST_ATTACHMENT,
})

TEST_STORED_DELETED_MESSAGE = create_stored_message_json(
    [{"value": TEST_MESSAGE_TEXT, "create_time": TEST_TIME}], deleted=True
)

CREATED_INDEX_KEY_FORMAT = CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY
DELETED_INDEX_KEY_FORMAT = DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY

TEST_INDEX_REDIS_KEY = CREATED_INDEX_KEY_FORMAT.format(
    space_id=TEST_SPACE_ID, sender_ldap=TEST_SENDER_LDAP
)
TEST_DELETED_INDEX_REDIS_KEY = DELETED_INDEX_KEY_FORMAT.format(
    space_id=TEST_SPACE_ID, sender_ldap=TEST_SENDER_LDAP
)

REDIS_MEMBER = TEST_MESSAGE_ID
TEST_SCORE = datetime.fromisoformat(TEST_TIME.replace("Z", "+00:00")).timestamp()


class TestGoogleChatMessagesUtils(TestCase):
    def setUp(self):
        # Mocks
        self.mock_logger = Mock()
        self.mock_redis = Mock()
        self.mock_pipe = Mock()
        self.mock_redis.pipeline.return_value = self.mock_pipe

        self.mock_retry = Mock()
        # make retry call the function it receives
        self.mock_retry.get_retry_on_transient.side_effect = lambda fn: fn()

        # System under test
        self.utils = GoogleChatMessagesUtils(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            retry_utils=self.mock_retry,
        )

    def test_store_created_messages_success(self):
        self.utils.store_messages(
            ldaps_dict=TEST_MOCK_LDAP_MAPPING,
            batch_messages=[TEST_MOCK_CREATED_MESSAGE_PAYLOAD],
            message_type=GoogleChatEventType.CREATED,
        )

        self.mock_redis.pipeline.assert_called_once()
        self.mock_pipe.zadd.assert_called_once_with(
            TEST_INDEX_REDIS_KEY, {REDIS_MEMBER: TEST_SCORE}
        )
        self.mock_pipe.set.assert_called_once_with(
            TEST_MESSAGE_NAME, TEST_STORED_CREATED_MESSAGE
        )
        self.mock_retry.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
        )
        self.mock_pipe.execute.assert_called_once()
        self.mock_logger.debug.assert_any_call(
            "ZADD %s {%s: %s}", TEST_INDEX_REDIS_KEY, REDIS_MEMBER, TEST_SCORE
        )
        self.mock_logger.debug.assert_any_call("SET %s created", TEST_MESSAGE_NAME)

    def test_store_updated_messages_success(self):
        self.mock_redis.get.return_value = TEST_STORED_UPDATED_MESSAGE_PRE_UPDATE

        self.utils.store_messages(
            ldaps_dict={},  # ldaps_dict is not needed for updates
            batch_messages=[TEST_MOCK_UPDATED_MESSAGE_PAYLOAD],
            message_type=GoogleChatEventType.UPDATED,
        )

        self.mock_redis.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_pipe.set.assert_called_once_with(
            TEST_MESSAGE_NAME, TEST_STORED_UPDATED_MESSAGE_POST_UPDATE
        )
        self.mock_pipe.execute.assert_called_once()
        self.mock_retry.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
        )
        self.mock_logger.debug.assert_any_call("SET %s updated", TEST_MESSAGE_NAME)

    def test_store_deleted_messages_success(self):
        self.mock_redis.get.return_value = TEST_STORED_CREATED_MESSAGE
        self.mock_redis.zscore.return_value = TEST_SCORE

        self.utils.store_messages(
            ldaps_dict={},  # ldaps_dict is not needed for deletes
            batch_messages=[TEST_MOCK_DELETED_MESSAGE_PAYLOAD],
            message_type=GoogleChatEventType.DELETED,
        )

        self.mock_redis.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis.zscore.assert_called_once_with(
            TEST_INDEX_REDIS_KEY, REDIS_MEMBER
        )
        self.mock_pipe.set.assert_called_once_with(
            TEST_MESSAGE_NAME, TEST_STORED_DELETED_MESSAGE
        )
        self.mock_pipe.zrem.assert_called_once_with(TEST_INDEX_REDIS_KEY, REDIS_MEMBER)
        self.mock_pipe.zadd.assert_called_once_with(
            TEST_DELETED_INDEX_REDIS_KEY, {REDIS_MEMBER: float(TEST_SCORE)}
        )
        self.mock_retry.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
        )
        self.mock_pipe.execute.assert_called_once()

    def test_store_updated_message_does_not_exist(self):
        self.mock_redis.get.return_value = None

        self.utils.store_messages(
            ldaps_dict={},
            batch_messages=[TEST_MOCK_UPDATED_MESSAGE_PAYLOAD],
            message_type=GoogleChatEventType.UPDATED,
        )

        self.mock_redis.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_pipe.set.assert_not_called()
        self.mock_pipe.execute.assert_called_once()
        self.mock_retry.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
        )

    def test_store_updated_message_missing_text_is_handled(self):
        """
        Old code raised TypeError when 'text' wasn't a list.
        New code treats missing/None 'text' as empty and proceeds.
        """
        self.mock_redis.get.return_value = TEST_STORED_INVALID_UPDATED_MESSAGE

        self.utils.store_messages(
            ldaps_dict={},
            batch_messages=[TEST_MOCK_UPDATED_MESSAGE_PAYLOAD],
            message_type=GoogleChatEventType.UPDATED,
        )

        self.mock_redis.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_pipe.set.assert_called_once()

        args, _ = self.mock_pipe.set.call_args
        self.assertEqual(args[0], TEST_MESSAGE_NAME)

        stored_json = args[1]
        parsed = json.loads(stored_json)
        self.assertIsInstance(parsed.get("text"), list)
        self.assertGreaterEqual(len(parsed["text"]), 1)
        self.assertEqual(parsed["text"][-1]["createTime"], TEST_TIME)
        self.assertEqual(parsed["text"][-1]["value"], TEST_MESSAGE_TEXT)
        self.mock_pipe.execute.assert_called_once()
        self.mock_retry.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
        )

    def test_store_deleted_message_does_not_exist(self):
        self.mock_redis.get.return_value = None

        self.utils.store_messages(
            ldaps_dict={},
            batch_messages=[TEST_MOCK_DELETED_MESSAGE_PAYLOAD],
            message_type=GoogleChatEventType.DELETED,
        )

        self.mock_redis.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_pipe.zrem.assert_not_called()
        self.mock_pipe.set.assert_not_called()
        self.mock_pipe.zadd.assert_not_called()
        self.mock_pipe.execute.assert_called_once()
        self.mock_retry.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
        )

    def test_store_deleted_message_already_deleted(self):
        self.mock_redis.get.return_value = (
            TEST_STORED_DELETED_MESSAGE  # Message is already deleted
        )
        self.mock_redis.zscore.return_value = TEST_SCORE  # zscore might or might not be called, depending on internal logic. If not, it's fine.

        self.utils.store_messages(
            ldaps_dict={},
            batch_messages=[TEST_MOCK_DELETED_MESSAGE_PAYLOAD],
            message_type=GoogleChatEventType.DELETED,
        )

        self.mock_redis.get.assert_called_once_with(TEST_MESSAGE_NAME)
        self.mock_redis.zscore.assert_not_called()  # Should not call zscore if already deleted
        self.mock_pipe.set.assert_not_called()
        self.mock_pipe.zrem.assert_not_called()
        self.mock_pipe.zadd.assert_not_called()
        self.mock_pipe.execute.assert_called_once()  # Pipeline execute will still be called
        self.mock_retry.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
        )

    def test_store_created_message_invalid_format(self):
        invalid_payload = {"message": {"sender": TEST_USER}}
        with self.assertRaises(ValueError):
            self.utils.store_messages(
                ldaps_dict=TEST_MOCK_LDAP_MAPPING,
                batch_messages=[invalid_payload],
                message_type=GoogleChatEventType.CREATED,
            )

        self.mock_pipe.zadd.assert_not_called()
        self.mock_pipe.set.assert_not_called()
        self.mock_pipe.execute.assert_not_called()

    def test_store_created_message_without_sender_ldap(self):
        missing_ldap_mapping = {
            "users/some_other_user": "some_ldap"
        }  # TEST_USER["name"] is not in this dict
        self.utils.store_messages(
            ldaps_dict=missing_ldap_mapping,
            batch_messages=[TEST_MOCK_CREATED_MESSAGE_PAYLOAD],
            message_type=GoogleChatEventType.CREATED,
        )

        self.mock_pipe.zadd.assert_not_called()
        self.mock_pipe.set.assert_not_called()
        self.mock_pipe.execute.assert_called_once()
        self.mock_retry.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
        )

    def test_sync_batch_created_messages(self):
        # sync_batch_created_messages expects raw message data, not the "message" wrapper
        raw_message_data = TEST_MOCK_CREATED_MESSAGE_PAYLOAD["message"]

        self.utils.sync_batch_created_messages(
            [raw_message_data, raw_message_data],  # Two identical messages
            {
                "test_user": TEST_SENDER_LDAP
            },  # ldap_mapping should map 'test_user' (from sender_id) to TEST_SENDER_LDAP
        )

        self.mock_redis.pipeline.assert_called_once()
        self.assertEqual(self.mock_pipe.zadd.call_count, 2)
        self.assertEqual(self.mock_pipe.set.call_count, 2)
        self.mock_retry.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
        )
        self.mock_pipe.execute.assert_called_once()

    def test_sync_batch_created_messages_pipeline_failure(self):
        self.mock_pipe.execute.side_effect = Exception("Redis is down")
        raw_message_data = TEST_MOCK_CREATED_MESSAGE_PAYLOAD["message"]

        with self.assertRaises(RuntimeError):
            self.utils.sync_batch_created_messages(
                [raw_message_data, raw_message_data],
                {
                    "test_user": TEST_SENDER_LDAP
                },  # ldap_mapping should map 'test_user' (from sender_id) to TEST_SENDER_LDAP
            )

        self.mock_pipe.execute.assert_called_once()

    def test_sync_batch_created_messages_with_invalid_params(self):
        # Test cases where ldaps_dict is missing or messages_list is empty/None
        invalid_cases = [
            ([], {"test_user": TEST_SENDER_LDAP}),  # Empty messages_list
            ([TEST_MOCK_CREATED_MESSAGE_PAYLOAD["message"]], {}),  # Empty ldaps_dict
            ([TEST_MOCK_CREATED_MESSAGE_PAYLOAD["message"]], None),  # None ldaps_dict
            ([], None),  # Both empty
            (None, {"test_user": TEST_SENDER_LDAP}),  # None messages_list
            (None, None),  # Both None
        ]

        for messages, ldap_mapping in invalid_cases:
            with self.assertRaises(ValueError):
                self.utils.sync_batch_created_messages(messages, ldap_mapping)


if __name__ == "__main__":
    main()
