import json
from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

from backend.utils.microsoft_chat_message_store import (
    _get_ldap_by_id,
    _format_datetime_to_iso_utc_z,
    _process_attachments,
    _handle_deleted_message,
    _handle_created_messages,
    _handle_update_message,
    sync_near_real_time_message_to_redis,
    sync_history_chat_messages_to_redis,
    MicrosoftChatMessagesChangeType,
    MicrosoftChatMessageAttachmentType,
    ChatMessageType,
)


class TestMicrosoftChatMessageStore(IsolatedAsyncioTestCase):
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
        message_type=ChatMessageType.Message,
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
        message_type=ChatMessageType.Message,
        created_date_time=TEST_DATATIME,
        last_modified_date_time=TEST_DATATIME,
        deleted_date_time=TEST_DATATIME,
        body=None,
        attachments=None,
        from_=SimpleNamespace(user=SimpleNamespace(id=TEST_USER_ID)),
    )
    TEST_SYSTEM_MESSAGE = SimpleNamespace(
        id=TEST_MESSAGE_ID, message_type=ChatMessageType.SystemEventMessage
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

    async def test_get_ldap_by_id_success(self):
        mock_graph_client = MagicMock()
        mock_graph_client.users.by_user_id.return_value.get = AsyncMock()
        mock_graph_client.users.by_user_id.return_value.get.return_value.mail = (
            self.TEST_USER_EMAIL
        )

        ldap = await _get_ldap_by_id(self.TEST_USER_ID, mock_graph_client)
        self.assertEqual(ldap, self.TEST_USER_LDAP)

    async def test_get_ldap_by_id_no_client(self):
        with self.assertRaises(ValueError):
            await _get_ldap_by_id(self.TEST_USER_ID, None)

    def test_format_datetime_to_iso_utc_z(self):
        iso_str = _format_datetime_to_iso_utc_z(self.TEST_DATATIME)
        self.assertEqual(iso_str, self.TEST_FORMATED_DATETIME)

    def test_process_attachments(self):
        class Attachment:
            def __init__(self, content_type, content_url=None, id=None):
                self.content_type = content_type
                self.content_url = content_url
                self.id = id

        attachments = [
            Attachment(
                MicrosoftChatMessageAttachmentType.REFERENCE_LINK.value,
                content_url=self.TEST_ATTACHMENT_REFERENCE_URI,
            ),
            Attachment(
                MicrosoftChatMessageAttachmentType.MESSAGE_REFERENCE.value,
                id=self.TEST_ATTACHMENT_MESSAGE_REFERENCE_ID,
            ),
        ]

        processed_urls, reply_to_id = _process_attachments(
            attachments, self.TEST_MESSAGE_ID
        )
        self.assertEqual(processed_urls, [self.TEST_ATTACHMENT_REFERENCE_URI])
        self.assertEqual(reply_to_id, self.TEST_ATTACHMENT_MESSAGE_REFERENCE_ID)

    def test_handle_deleted_message_calls_pipeline_correctly(self):
        mock_pipeline = MagicMock()
        _handle_deleted_message(
            self.TEST_MESSAGE_ID, self.TEST_USER_LDAP, self.TEST_SCORE, mock_pipeline
        )
        mock_pipeline.zrem.assert_called_once()
        mock_pipeline.zadd.assert_called_once()

    def test_handle_created_messages_calls_pipeline_correctly(self):
        mock_pipeline = MagicMock()
        _handle_created_messages(self.TEST_MESSAGE, self.TEST_USER_LDAP, mock_pipeline)
        mock_pipeline.zadd.assert_called_once()
        mock_pipeline.set.assert_called_once()

    def test_handle_update_message_updates_pipeline(self):
        mock_pipeline = MagicMock()
        mock_redis_client = MagicMock()
        mock_redis_client.zscore.return_value = self.TEST_SCORE
        mock_redis_client.get.return_value = json.dumps(self.TEST_SAVED_MESSAGE_DICT)

        _handle_update_message(
            self.TEST_MESSAGE, self.TEST_USER_LDAP, mock_pipeline, mock_redis_client
        )
        mock_pipeline.set.assert_called_once()

    def test_handle_update_message_undo_pipeline(self):
        mock_pipeline = MagicMock()
        mock_redis_client = MagicMock()
        mock_redis_client.zscore.side_effect = [None, self.TEST_SCORE]

        _handle_update_message(
            self.TEST_MESSAGE, self.TEST_USER_LDAP, mock_pipeline, mock_redis_client
        )
        mock_pipeline.zrem.assert_called_once()
        mock_pipeline.zadd.assert_called_once()

    async def test_sync_near_real_time_message_to_redis_invalid_inputs(self):
        for case in self.TEST_INVALID_INPUT_CASES:
            with self.subTest(
                change_type=case["change_type"], resource=case["resource"]
            ):
                with self.assertRaises(ValueError):
                    await sync_near_real_time_message_to_redis(
                        change_type=case["change_type"], resource=case["resource"]
                    )

    @patch("backend.utils.microsoft_chat_message_store.MicrosoftClientFactory")
    @patch("backend.utils.microsoft_chat_message_store.RedisClientFactory")
    @patch("backend.utils.microsoft_chat_message_store._get_ldap_by_id")
    @patch("backend.utils.microsoft_chat_message_store._handle_created_messages")
    @patch("backend.utils.microsoft_chat_message_store._handle_deleted_message")
    @patch("backend.utils.microsoft_chat_message_store._handle_update_message")
    @patch("backend.utils.microsoft_chat_message_store._execute_request")
    async def test_sync_near_real_time_message_to_redis_created(
        self,
        mock_execute,
        mock_handle_update,
        mock_handle_deleted,
        mock_handle_created,
        mock_get_ldap,
        mock_redis_factory,
        mock_graph_factory,
    ):
        mock_get = AsyncMock(return_value=self.TEST_MESSAGE)
        mock_message_accessor = MagicMock(get=mock_get)
        mock_messages = MagicMock(
            by_chat_message_id=MagicMock(return_value=mock_message_accessor)
        )
        mock_chat = MagicMock(messages=mock_messages)
        mock_chats = MagicMock(by_chat_id=MagicMock(return_value=mock_chat))
        mock_graph_client = MagicMock(chats=mock_chats)
        mock_graph_factory.return_value.create_graph_service_client.return_value = (
            mock_graph_client
        )

        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = (
            mock_redis_client
        )

        mock_get_ldap.return_value = self.TEST_USER_LDAP

        await sync_near_real_time_message_to_redis(
            MicrosoftChatMessagesChangeType.CREATED.value, self.TEST_RESOURCE
        )

        mock_handle_created.assert_called_once()
        mock_handle_update.assert_not_called()
        mock_handle_deleted.assert_not_called()

    @patch("backend.utils.microsoft_chat_message_store.MicrosoftClientFactory")
    @patch("backend.utils.microsoft_chat_message_store.RedisClientFactory")
    @patch("backend.utils.microsoft_chat_message_store._get_ldap_by_id")
    @patch("backend.utils.microsoft_chat_message_store._handle_created_messages")
    @patch("backend.utils.microsoft_chat_message_store._handle_deleted_message")
    @patch("backend.utils.microsoft_chat_message_store._handle_update_message")
    @patch("backend.utils.microsoft_chat_message_store._execute_request")
    async def test_sync_near_real_time_message_to_redis_updated(
        self,
        mock_execute,
        mock_handle_update,
        mock_handle_deleted,
        mock_handle_created,
        mock_get_ldap,
        mock_redis_factory,
        mock_graph_factory,
    ):
        mock_get = AsyncMock(return_value=self.TEST_MESSAGE)
        mock_message_accessor = MagicMock(get=mock_get)
        mock_messages = MagicMock(
            by_chat_message_id=MagicMock(return_value=mock_message_accessor)
        )
        mock_chat = MagicMock(messages=mock_messages)
        mock_chats = MagicMock(by_chat_id=MagicMock(return_value=mock_chat))
        mock_graph_client = MagicMock(chats=mock_chats)
        mock_graph_factory.return_value.create_graph_service_client.return_value = (
            mock_graph_client
        )

        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = (
            mock_redis_client
        )

        mock_get_ldap.return_value = self.TEST_USER_LDAP

        await sync_near_real_time_message_to_redis(
            MicrosoftChatMessagesChangeType.UPDATED.value, self.TEST_RESOURCE
        )

        mock_handle_created.assert_not_called()
        mock_handle_update.assert_called_once()
        mock_handle_deleted.assert_not_called()

    @patch("backend.utils.microsoft_chat_message_store.MicrosoftClientFactory")
    @patch("backend.utils.microsoft_chat_message_store.RedisClientFactory")
    @patch("backend.utils.microsoft_chat_message_store._get_ldap_by_id")
    @patch("backend.utils.microsoft_chat_message_store._handle_created_messages")
    @patch("backend.utils.microsoft_chat_message_store._handle_deleted_message")
    @patch("backend.utils.microsoft_chat_message_store._handle_update_message")
    @patch("backend.utils.microsoft_chat_message_store._execute_request")
    async def test_sync_near_real_time_message_to_redis_deleted(
        self,
        mock_execute,
        mock_handle_update,
        mock_handle_deleted,
        mock_handle_created,
        mock_get_ldap,
        mock_redis_factory,
        mock_graph_factory,
    ):
        mock_get = AsyncMock(return_value=self.TEST_MESSAGE)
        mock_message_accessor = MagicMock(get=mock_get)
        mock_messages = MagicMock(
            by_chat_message_id=MagicMock(return_value=mock_message_accessor)
        )
        mock_chat = MagicMock(messages=mock_messages)
        mock_chats = MagicMock(by_chat_id=MagicMock(return_value=mock_chat))
        mock_graph_client = MagicMock(chats=mock_chats)
        mock_graph_factory.return_value.create_graph_service_client.return_value = (
            mock_graph_client
        )

        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_redis_client.zscore.return_value = self.TEST_SCORE
        mock_redis_factory.return_value.create_redis_client.return_value = (
            mock_redis_client
        )

        mock_get_ldap.return_value = self.TEST_USER_LDAP

        await sync_near_real_time_message_to_redis(
            MicrosoftChatMessagesChangeType.DELETED.value, self.TEST_RESOURCE
        )

        mock_handle_created.assert_not_called()
        mock_handle_update.assert_not_called()
        mock_handle_deleted.assert_called_once()

    @patch("backend.utils.microsoft_chat_message_store.MicrosoftClientFactory")
    @patch("backend.utils.microsoft_chat_message_store.RedisClientFactory")
    @patch("backend.utils.microsoft_chat_message_store._get_ldap_by_id")
    @patch("backend.utils.microsoft_chat_message_store._handle_created_messages")
    @patch("backend.utils.microsoft_chat_message_store._handle_deleted_message")
    @patch("backend.utils.microsoft_chat_message_store._handle_update_message")
    @patch("backend.utils.microsoft_chat_message_store._execute_request")
    async def test_sync_near_real_time_message_to_redis_deleted_but_data_inconsistency(
        self,
        mock_execute,
        mock_handle_update,
        mock_handle_deleted,
        mock_handle_created,
        mock_get_ldap,
        mock_redis_factory,
        mock_graph_factory,
    ):
        mock_get = AsyncMock(return_value=self.TEST_MESSAGE)
        mock_message_accessor = MagicMock(get=mock_get)
        mock_messages = MagicMock(
            by_chat_message_id=MagicMock(return_value=mock_message_accessor)
        )
        mock_chat = MagicMock(messages=mock_messages)
        mock_chats = MagicMock(by_chat_id=MagicMock(return_value=mock_chat))
        mock_graph_client = MagicMock(chats=mock_chats)
        mock_graph_factory.return_value.create_graph_service_client.return_value = (
            mock_graph_client
        )

        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_redis_client.zscore.return_value = None
        mock_redis_factory.return_value.create_redis_client.return_value = (
            mock_redis_client
        )

        mock_get_ldap.return_value = self.TEST_USER_LDAP

        with self.assertRaises(ValueError):
            await sync_near_real_time_message_to_redis(
                MicrosoftChatMessagesChangeType.DELETED.value, self.TEST_RESOURCE
            )

        mock_handle_created.assert_not_called()
        mock_handle_update.assert_not_called()
        mock_handle_deleted.assert_not_called()

    @patch("backend.utils.microsoft_chat_message_store._execute_request")
    @patch("backend.utils.microsoft_chat_message_store._handle_created_messages")
    @patch("backend.utils.microsoft_chat_message_store.RedisClientFactory")
    def test_sync_messages(self, mock_factory, mock_handle_created, mock_execute):
        messages = [
            self.TEST_SYSTEM_MESSAGE,
            self.TEST_DELETED_MESSAGE,
            self.TEST_MESSAGE,
        ]

        processed, skipped = sync_history_chat_messages_to_redis(
            messages, self.TEST_ALL_LDAPS
        )

        self.assertEqual(processed, 1)
        self.assertEqual(skipped, 2)

        mock_handle_created.assert_called_once()
        mock_execute.assert_called_once()

    @patch("backend.utils.microsoft_chat_message_store.RedisClientFactory")
    def test_empty_messages_raises(self, mock_factory):
        with self.assertRaises(ValueError):
            sync_history_chat_messages_to_redis([], self.TEST_ALL_LDAPS)

    @patch("backend.utils.microsoft_chat_message_store.RedisClientFactory")
    def test_empty_ldap_raises(self, mock_factory):
        with self.assertRaises(ValueError):
            sync_history_chat_messages_to_redis([self.TEST_SYSTEM_MESSAGE], {})

    @patch("backend.utils.microsoft_chat_message_store.RedisClientFactory")
    def test_redis_client_none_raises(self, mock_factory):
        mock_factory().create_redis_client.return_value = None
        with self.assertRaises(ValueError):
            sync_history_chat_messages_to_redis(
                [self.TEST_SYSTEM_MESSAGE], self.TEST_ALL_LDAPS
            )


if __name__ == "__main__":
    main()
