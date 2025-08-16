import json
from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from backend.common.constants import (
    MicrosoftChatMessagesChangeType,
    MICROSOFT_CHAT_MESSAGES_INDEX_KEY,
    MICROSOFT_CHAT_MESSAGES_DETAILS_KEY,
    MicrosoftChatMessageAttachmentType,
    MicrosoftChatMessageType,
)
from backend.utils.microsoft_chat_message_util import (
    MicrosoftChatMessageUtil,
    TextContent,
)


class TestMicrosoftChatMessageUtil(IsolatedAsyncioTestCase):
    TEST_USER_EMAIL = "foo@example.com"
    TEST_USER_LDAP = "foo"
    TEST_USER_ID = "23157831233"
    TEST_DATATIME = datetime(2023, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
    TEST_FORMATED_DATETIME = "2023-01-01T12:00:00.123456Z"
    TEST_ATTACHMENT_REFERENCE_URI = "https://example.com/file.pdf"
    TEST_ATTACHMENT_MESSAGE_REFERENCE_ID = "msg123"
    TEST_MESSAGE_ID = "msg124"
    TEST_SCORE = 123.456
    TEST_MESSAGE_CONTENT = "old content"
    TEST_MESSAGE_CREATE_TIME = "2023-01-01T00:00:00Z"
    TEST_MESSAGE = SimpleNamespace(
        id=TEST_MESSAGE_ID,
        message_type=MicrosoftChatMessageType.Message,
        created_date_time=TEST_DATATIME,
        last_modified_date_time=TEST_DATATIME,
        deleted_date_time=None,
        body=SimpleNamespace(content_type="text", content="Hello world"),
        attachments=[
            SimpleNamespace(
                content_type=MicrosoftChatMessageAttachmentType.REFERENCE_LINK.value,
                content_url=TEST_ATTACHMENT_REFERENCE_URI,
            ),
            SimpleNamespace(
                id=TEST_ATTACHMENT_MESSAGE_REFERENCE_ID,
                content_type=MicrosoftChatMessageAttachmentType.MESSAGE_REFERENCE.value,
            ),
        ],
        from_=SimpleNamespace(user=SimpleNamespace(id=TEST_USER_ID)),
    )
    TEST_DELETED_MESSAGE = SimpleNamespace(
        id=TEST_MESSAGE_ID,
        message_type=MicrosoftChatMessageType.Message,
        created_date_time=TEST_DATATIME,
        last_modified_date_time=TEST_DATATIME,
        deleted_date_time=TEST_DATATIME,
        body=None,
        attachments=None,
        from_=SimpleNamespace(user=SimpleNamespace(id=TEST_USER_ID)),
    )
    TEST_SYSTEM_MESSAGE = SimpleNamespace(
        id=TEST_MESSAGE_ID, message_type=MicrosoftChatMessageType.SystemEventMessage
    )
    TEST_SAVED_MESSAGE_DICT = {
        "sender": TEST_USER_LDAP,
        "text": [
            {"value": TEST_MESSAGE_CONTENT, "create_time": TEST_MESSAGE_CREATE_TIME}
        ],
        "reply_to": None,
        "attachment": [],
    }
    TEST_RESOURCE = f"chats('3109285043531')/messages('{TEST_MESSAGE_ID}')"
    TEST_INVALID_INPUT_CASES = [
        {"change_type": None, "resource": None},
        {"change_type": None, "resource": ""},
        {"change_type": "", "resource": None},
        {"change_type": "", "resource": ""},
        {"change_type": "", "resource": TEST_RESOURCE},
        {"change_type": "unsupported_type", "resource": TEST_RESOURCE},
    ]
    TEST_ALL_LDAPS = {TEST_USER_ID: TEST_USER_LDAP}

    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_redis_client = MagicMock()
        self.mock_microsoft_service = AsyncMock()
        self.mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = self.mock_pipeline
        self.mock_date_time_util = MagicMock()
        self.mock_date_time_util.format_datetime_to_iso_utc_z.return_value = (
            self.TEST_FORMATED_DATETIME
        )
        self.mock_retry_utils = MagicMock()
        self.microsoft_chat_message_util = MicrosoftChatMessageUtil(
            logger=self.mock_logger,
            redis_client=self.mock_redis_client,
            microsoft_service=self.mock_microsoft_service,
            date_time_util=self.mock_date_time_util,
            retry_utils=self.mock_retry_utils,
        )

    def make_attachment(self, content_type, content_url=None, id=None):
        attachment = MagicMock()
        attachment.content_type = content_type
        attachment.content_url = content_url
        attachment.id = id
        return attachment

    def test_synchronizer_init_invalid_logger(self):
        MicrosoftChatMessageUtil(
            logger=None,
            redis_client=MagicMock(),
            microsoft_service=MagicMock(),
            date_time_util=MagicMock(),
            retry_utils=MagicMock(),
        )

    def test_process_attachments(self):
        attachments = [
            self.make_attachment(
                MicrosoftChatMessageAttachmentType.REFERENCE_LINK.value,
                content_url=self.TEST_ATTACHMENT_REFERENCE_URI,
            ),
            self.make_attachment(
                MicrosoftChatMessageAttachmentType.MESSAGE_REFERENCE.value,
                id=self.TEST_ATTACHMENT_MESSAGE_REFERENCE_ID,
            ),
            self.make_attachment("unsupported_type", id="unsupported_attachment_id"),
        ]

        processed_urls, reply_to_id = (
            self.microsoft_chat_message_util._process_attachments(
                attachments, self.TEST_MESSAGE_ID
            )
        )

        self.assertEqual(processed_urls, [self.TEST_ATTACHMENT_REFERENCE_URI])
        self.assertEqual(reply_to_id, self.TEST_ATTACHMENT_MESSAGE_REFERENCE_ID)

    def test_handle_deleted_message_calls_pipeline_correctly(self):
        self.microsoft_chat_message_util._handle_deleted_message(
            self.TEST_MESSAGE_ID,
            self.TEST_USER_LDAP,
            self.TEST_SCORE,
            self.mock_pipeline,
        )

        created_index_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.CREATED.value,
            sender_ldap=self.TEST_USER_LDAP,
        )
        deleted_index_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.DELETED.value,
            sender_ldap=self.TEST_USER_LDAP,
        )
        self.mock_pipeline.zrem.assert_called_once_with(
            created_index_key, self.TEST_MESSAGE_ID
        )
        self.mock_pipeline.zadd.assert_called_once_with(
            deleted_index_key, {self.TEST_MESSAGE_ID: self.TEST_SCORE}
        )

    def test_handle_deleted_message_input_validation(self):
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_deleted_message(
                None, self.TEST_USER_LDAP, self.TEST_SCORE, self.mock_pipeline
            )
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_deleted_message(
                self.TEST_MESSAGE_ID, None, self.TEST_SCORE, self.mock_pipeline
            )
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_deleted_message(
                self.TEST_MESSAGE_ID, self.TEST_USER_LDAP, None, self.mock_pipeline
            )
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_deleted_message(
                self.TEST_MESSAGE_ID, self.TEST_USER_LDAP, self.TEST_SCORE, None
            )

    def test_handle_created_messages_calls_pipeline_correctly(self):
        self.microsoft_chat_message_util._handle_created_messages(
            self.TEST_MESSAGE, self.TEST_USER_LDAP, self.mock_pipeline
        )

        index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.CREATED.value,
            sender_ldap=self.TEST_USER_LDAP,
        )
        detail_key = MICROSOFT_CHAT_MESSAGES_DETAILS_KEY.format(
            message_id=self.TEST_MESSAGE_ID
        )
        index_score = self.TEST_DATATIME.timestamp()
        self.mock_pipeline.zadd.assert_called_once_with(
            index_redis_key, {self.TEST_MESSAGE_ID: index_score}
        )
        self.mock_pipeline.set.assert_called_once()
        args, _ = self.mock_pipeline.set.call_args
        self.assertEqual(args[0], detail_key)
        saved_message_dict = json.loads(args[1])
        expected_text_content = TextContent(
            value="Hello world", create_time=self.TEST_FORMATED_DATETIME
        ).to_dict()
        self.assertEqual(saved_message_dict["sender"], self.TEST_USER_LDAP)
        self.assertEqual(saved_message_dict["text"], [expected_text_content])
        self.assertEqual(
            saved_message_dict["attachment"], [self.TEST_ATTACHMENT_REFERENCE_URI]
        )
        self.assertEqual(
            saved_message_dict["reply_to"], self.TEST_ATTACHMENT_MESSAGE_REFERENCE_ID
        )

    def test_handle_created_messages_input_validation(self):
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_created_messages(
                None, self.TEST_USER_LDAP, self.mock_pipeline
            )
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_created_messages(
                self.TEST_MESSAGE, None, self.mock_pipeline
            )
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_created_messages(
                self.TEST_MESSAGE, self.TEST_USER_LDAP, None
            )

    def test_handle_update_message_updates_pipeline(self):
        self.mock_redis_client.zscore.return_value = self.TEST_SCORE
        self.mock_redis_client.get.return_value = json.dumps(
            self.TEST_SAVED_MESSAGE_DICT
        )

        self.microsoft_chat_message_util._handle_update_message(
            self.TEST_MESSAGE, self.TEST_USER_LDAP, self.mock_pipeline
        )

        detail_key = MICROSOFT_CHAT_MESSAGES_DETAILS_KEY.format(
            message_id=self.TEST_MESSAGE_ID
        )
        self.mock_pipeline.set.assert_called_once()
        args, _ = self.mock_pipeline.set.call_args
        self.assertEqual(args[0], detail_key)
        updated_data = json.loads(args[1])
        self.assertEqual(len(updated_data["text"]), 2)
        self.assertEqual(
            updated_data["text"][-1]["value"], self.TEST_MESSAGE.body.content
        )
        self.assertEqual(
            updated_data["text"][-1]["create_time"], self.TEST_FORMATED_DATETIME
        )
        self.assertIn(self.TEST_ATTACHMENT_REFERENCE_URI, updated_data["attachment"])
        self.assertEqual(
            updated_data["reply_to"], self.TEST_ATTACHMENT_MESSAGE_REFERENCE_ID
        )

    def test_handle_update_message_undo_pipeline(self):
        self.mock_redis_client.zscore.side_effect = [None, self.TEST_SCORE]

        self.microsoft_chat_message_util._handle_update_message(
            self.TEST_MESSAGE, self.TEST_USER_LDAP, self.mock_pipeline
        )

        deleted_index_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.DELETED.value,
            sender_ldap=self.TEST_USER_LDAP,
        )
        created_index_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.CREATED.value,
            sender_ldap=self.TEST_USER_LDAP,
        )
        self.mock_redis_client.zscore.assert_any_call(
            created_index_key, self.TEST_MESSAGE_ID
        )
        self.mock_redis_client.zscore.assert_any_call(
            deleted_index_key, self.TEST_MESSAGE_ID
        )
        self.mock_pipeline.zrem.assert_called_once_with(
            deleted_index_key, self.TEST_MESSAGE_ID
        )
        self.mock_pipeline.zadd.assert_called_once_with(
            created_index_key, {self.TEST_MESSAGE_ID: self.TEST_SCORE}
        )

    def test_handle_update_message_not_found_in_any_index_raises(self):
        self.mock_redis_client.zscore.side_effect = [None, None]
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_update_message(
                self.TEST_MESSAGE, self.TEST_USER_LDAP, self.mock_pipeline
            )

    def test_handle_update_message_no_saved_data_raises(self):
        self.mock_redis_client.zscore.return_value = self.TEST_SCORE
        self.mock_redis_client.get.return_value = None

        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_update_message(
                self.TEST_MESSAGE, self.TEST_USER_LDAP, self.mock_pipeline
            )

    def test_handle_update_message_input_validation(self):
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_update_message(
                None, self.TEST_USER_LDAP, self.mock_pipeline
            )
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_update_message(
                self.TEST_MESSAGE, None, self.mock_pipeline
            )
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util._handle_update_message(
                self.TEST_MESSAGE, self.TEST_USER_LDAP, None
            )

    async def test_sync_near_real_time_message_to_redis_invalid_inputs(self):
        for case in self.TEST_INVALID_INPUT_CASES:
            with self.subTest(
                change_type=case["change_type"], resource=case["resource"]
            ):
                with self.assertRaises(ValueError):
                    await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
                        change_type=case["change_type"], resource=case["resource"]
                    )
        with self.assertRaises(ValueError):
            await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
                MicrosoftChatMessagesChangeType.CREATED.value, "invalid-resource-format"
            )

    @patch.object(
        MicrosoftChatMessageUtil, "_handle_created_messages", new_callable=MagicMock
    )
    @patch.object(
        MicrosoftChatMessageUtil, "_handle_deleted_message", new_callable=MagicMock
    )
    @patch.object(
        MicrosoftChatMessageUtil, "_handle_update_message", new_callable=MagicMock
    )
    async def test_sync_near_real_time_message_to_redis_created(
        self,
        mock_handle_update,
        mock_handle_deleted,
        mock_handle_created,
    ):
        self.mock_microsoft_service.get_message_by_id.return_value = self.TEST_MESSAGE
        self.mock_microsoft_service.get_ldap_by_id.return_value = self.TEST_USER_LDAP

        await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
            MicrosoftChatMessagesChangeType.CREATED.value, self.TEST_RESOURCE
        )

        self.mock_microsoft_service.get_message_by_id.assert_called_once()
        self.mock_microsoft_service.get_ldap_by_id.assert_called_once()
        mock_handle_created.assert_called_once_with(
            self.TEST_MESSAGE, self.TEST_USER_LDAP, self.mock_pipeline
        )
        mock_handle_update.assert_not_called()
        mock_handle_deleted.assert_not_called()

    @patch.object(
        MicrosoftChatMessageUtil, "_handle_created_messages", new_callable=MagicMock
    )
    @patch.object(
        MicrosoftChatMessageUtil, "_handle_deleted_message", new_callable=MagicMock
    )
    @patch.object(
        MicrosoftChatMessageUtil, "_handle_update_message", new_callable=MagicMock
    )
    async def test_sync_near_real_time_message_to_redis_updated(
        self,
        mock_handle_update,
        mock_handle_deleted,
        mock_handle_created,
    ):
        self.mock_microsoft_service.get_message_by_id.return_value = self.TEST_MESSAGE
        self.mock_microsoft_service.get_ldap_by_id.return_value = self.TEST_USER_LDAP

        await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
            MicrosoftChatMessagesChangeType.UPDATED.value, self.TEST_RESOURCE
        )

        self.mock_microsoft_service.get_message_by_id.assert_called_once()
        self.mock_microsoft_service.get_ldap_by_id.assert_called_once()
        mock_handle_created.assert_not_called()
        mock_handle_update.assert_called_once_with(
            self.TEST_MESSAGE, self.TEST_USER_LDAP, self.mock_pipeline
        )
        mock_handle_deleted.assert_not_called()

    @patch.object(
        MicrosoftChatMessageUtil, "_handle_created_messages", new_callable=MagicMock
    )
    @patch.object(
        MicrosoftChatMessageUtil, "_handle_deleted_message", new_callable=MagicMock
    )
    @patch.object(
        MicrosoftChatMessageUtil, "_handle_update_message", new_callable=MagicMock
    )
    async def test_sync_near_real_time_message_to_redis_deleted(
        self,
        mock_handle_update,
        mock_handle_deleted,
        mock_handle_created,
    ):
        self.mock_microsoft_service.get_message_by_id.return_value = self.TEST_MESSAGE
        self.mock_microsoft_service.get_ldap_by_id.return_value = self.TEST_USER_LDAP
        self.mock_redis_client.zscore.return_value = self.TEST_SCORE

        await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
            MicrosoftChatMessagesChangeType.DELETED.value, self.TEST_RESOURCE
        )

        self.mock_microsoft_service.get_message_by_id.assert_called_once()
        self.mock_microsoft_service.get_ldap_by_id.assert_called_once()
        mock_handle_created.assert_not_called()
        mock_handle_update.assert_not_called()
        mock_handle_deleted.assert_called_once_with(
            self.TEST_MESSAGE_ID,
            self.TEST_USER_LDAP,
            self.TEST_SCORE,
            self.mock_pipeline,
        )
        self.mock_redis_client.zscore.assert_called_once()

    @patch.object(
        MicrosoftChatMessageUtil, "_handle_created_messages", new_callable=MagicMock
    )
    @patch.object(
        MicrosoftChatMessageUtil, "_handle_deleted_message", new_callable=MagicMock
    )
    @patch.object(
        MicrosoftChatMessageUtil, "_handle_update_message", new_callable=MagicMock
    )
    async def test_sync_near_real_time_message_to_redis_deleted_but_data_inconsistency(
        self,
        mock_handle_update,
        mock_handle_deleted,
        mock_handle_created,
    ):
        self.mock_microsoft_service.get_message_by_id.return_value = self.TEST_MESSAGE
        self.mock_microsoft_service.get_ldap_by_id.return_value = self.TEST_USER_LDAP
        self.mock_redis_client.zscore.return_value = None

        with self.assertRaises(ValueError):
            await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
                MicrosoftChatMessagesChangeType.DELETED.value, self.TEST_RESOURCE
            )

        self.mock_microsoft_service.get_message_by_id.assert_called_once()
        self.mock_microsoft_service.get_ldap_by_id.assert_called_once()
        mock_handle_created.assert_not_called()
        mock_handle_update.assert_not_called()
        mock_handle_deleted.assert_not_called()

    async def test_sync_near_real_time_message_to_redis_system_message_skipped(self):
        self.mock_microsoft_service.get_message_by_id.return_value = (
            self.TEST_SYSTEM_MESSAGE
        )
        self.mock_microsoft_service.get_ldap_by_id.return_value = self.TEST_USER_LDAP

        await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
            MicrosoftChatMessagesChangeType.CREATED.value, self.TEST_RESOURCE
        )

        self.mock_microsoft_service.get_ldap_by_id.assert_not_called()

    async def test_sync_near_real_time_message_to_redis_external_sender_skipped(self):
        self.mock_microsoft_service.get_message_by_id.return_value = self.TEST_MESSAGE
        self.mock_microsoft_service.get_ldap_by_id.return_value = None

        await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
            MicrosoftChatMessagesChangeType.CREATED.value, self.TEST_RESOURCE
        )

        self.mock_microsoft_service.get_ldap_by_id.assert_called_once()

    async def test_sync_near_real_time_message_to_redis_redis_pipeline_failure(self):
        self.mock_microsoft_service.get_message_by_id.return_value = self.TEST_MESSAGE
        self.mock_microsoft_service.get_ldap_by_id.return_value = self.TEST_USER_LDAP
        mock_get_retry_on_transient = MagicMock(
            side_effect=Exception("Simulated Redis pipeline error")
        )
        self.microsoft_chat_message_util.retry_utils.get_retry_on_transient = (
            mock_get_retry_on_transient
        )

        with self.assertRaises(RuntimeError):
            await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
                MicrosoftChatMessagesChangeType.CREATED.value, self.TEST_RESOURCE
            )

        mock_get_retry_on_transient.assert_called_once_with(self.mock_pipeline.execute)

    @patch.object(MicrosoftChatMessageUtil, "_handle_created_messages")
    def test_sync_history_chat_messages_to_redis(self, mock_handle_created):
        messages = [
            self.TEST_SYSTEM_MESSAGE,  # Skipped: System message
            self.TEST_DELETED_MESSAGE,  # Skipped: Deleted message
            self.TEST_MESSAGE,  # Processed
        ]

        processed, skipped = (
            self.microsoft_chat_message_util.sync_history_chat_messages_to_redis(
                messages, self.TEST_ALL_LDAPS
            )
        )

        self.assertEqual(processed, 1)
        self.assertEqual(skipped, 2)
        mock_handle_created.assert_called_once_with(
            self.TEST_MESSAGE, self.TEST_USER_LDAP, self.mock_pipeline
        )
        self.mock_pipeline.execute.assert_called_once

    def test_sync_history_chat_messages_to_redis_empty_messages_raises(self):
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util.sync_history_chat_messages_to_redis(
                [], self.TEST_ALL_LDAPS
            )

    def test_sync_history_chat_messages_to_redis_empty_ldap_raises(self):
        with self.assertRaises(ValueError):
            self.microsoft_chat_message_util.sync_history_chat_messages_to_redis(
                [self.TEST_MESSAGE], {}
            )

    def test_sync_history_chat_messages_to_redis_pipeline_failure(self):
        mock_get_retry_on_transient = MagicMock(
            side_effect=Exception("History sync Redis error")
        )
        self.microsoft_chat_message_util.retry_utils.get_retry_on_transient = (
            mock_get_retry_on_transient
        )

        with self.assertRaises(Exception):
            self.microsoft_chat_message_util.sync_history_chat_messages_to_redis(
                [self.TEST_MESSAGE], self.TEST_ALL_LDAPS
            )

        mock_get_retry_on_transient.assert_called_once_with(self.mock_pipeline.execute)


if __name__ == "__main__":
    main()
