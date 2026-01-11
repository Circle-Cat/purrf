import os
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import patch, AsyncMock, MagicMock
from backend.internal_activity_service.microsoft_meeting_chat_topic_cache_service import (
    MicrosoftMeetingChatTopicCacheService,
)
from backend.common.environment_constants import (
    MICROSOFT_ADMIN_LDAP,
    MICROSOFT_USER_LDAP,
)


class TestMicrosoftMeetingChatTopicCacheService(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.redis_client = MagicMock()
        self.microsoft_service = AsyncMock()
        self.mock_retry_utils = MagicMock()

        self.mock_retry_utils.get_retry_on_transient.side_effect = (
            lambda func, *args, **kwargs: func(*args, **kwargs)
        )

        self.microsoft_meeting_chat_topic_cache_service = (
            MicrosoftMeetingChatTopicCacheService(
                logger=self.logger,
                redis_client=self.redis_client,
                microsoft_service=self.microsoft_service,
                retry_utils=self.mock_retry_utils,
            )
        )

        self.test_chat_topics = {
            "chat_id_1": "Topic 1",
        }
        self.test_user_ldap = "user"
        self.test_admin_ldap = "admin"
        self.test_ldap_id_mapping = {
            "id_1": self.test_user_ldap,
            "id_2": self.test_admin_ldap,
        }
        mock_organizer = MagicMock(id="id_2")
        mock_online_meeting_info = MagicMock(organizer=mock_organizer)
        self.mock_chat = MagicMock(
            id="chat_id_1",
            topic="Topic 1",
            chat_type="meeting",
            online_meeting_info=mock_online_meeting_info,
        )
        self.test_valided_chats_response = [self.mock_chat]
        self.test_no_chats_response = []

    async def test_get_microsoft_chat_topics_cache_hit(self):
        self.redis_client.hgetall.return_value = self.test_chat_topics

        result = await self.microsoft_meeting_chat_topic_cache_service.get_microsoft_chat_topics()

        self.redis_client.hgetall.assert_called_once()
        self.assertEqual(result, self.test_chat_topics)

    async def test_get_microsoft_chat_topics_cache_miss(self):
        self.redis_client.hgetall.return_value = None
        self.microsoft_meeting_chat_topic_cache_service.cache_chat_topics = AsyncMock(
            return_value=self.test_chat_topics
        )

        result = await self.microsoft_meeting_chat_topic_cache_service.get_microsoft_chat_topics()

        self.redis_client.hgetall.assert_called_once()
        self.microsoft_meeting_chat_topic_cache_service.cache_chat_topics.assert_called_once()
        self.assertEqual(result, self.test_chat_topics)

    async def test_cache_chat_topics_missing_env_vars(self):
        with self.assertRaises(ValueError):
            await self.microsoft_meeting_chat_topic_cache_service.cache_chat_topics()

    async def test_cache_chat_topics_invalided_ldap(self):
        with patch.dict(
            os.environ,
            {
                MICROSOFT_ADMIN_LDAP: "invalided_user",
                MICROSOFT_USER_LDAP: self.test_user_ldap,
            },
        ):
            self.microsoft_service.list_all_id_ldap_mapping = AsyncMock(
                return_value=self.test_ldap_id_mapping
            )
            with self.assertRaises(ValueError):
                await (
                    self.microsoft_meeting_chat_topic_cache_service.cache_chat_topics()
                )
            self.microsoft_service.list_all_id_ldap_mapping.assert_called_once()
            self.microsoft_service.get_user_chats_by_user_id.assert_not_called()

    async def test_cache_chat_topics_no_chats(self):
        with patch.dict(
            os.environ,
            {
                MICROSOFT_ADMIN_LDAP: self.test_admin_ldap,
                MICROSOFT_USER_LDAP: self.test_user_ldap,
            },
        ):
            self.microsoft_service.list_all_id_ldap_mapping = AsyncMock(
                return_value=self.test_ldap_id_mapping
            )
            self.microsoft_service.get_user_chats_by_user_id = AsyncMock(
                return_value=self.test_no_chats_response
            )

            with self.assertRaises(ValueError):
                await (
                    self.microsoft_meeting_chat_topic_cache_service.cache_chat_topics()
                )

            self.microsoft_service.list_all_id_ldap_mapping.assert_called_once()
            self.microsoft_service.get_user_chats_by_user_id.assert_called_once()
            self.redis_client.pipeline.assert_not_called()

    async def test_cache_chat_topics_success(self):
        with patch.dict(
            os.environ,
            {
                MICROSOFT_ADMIN_LDAP: self.test_admin_ldap,
                MICROSOFT_USER_LDAP: self.test_user_ldap,
            },
        ):
            self.microsoft_service.list_all_id_ldap_mapping = AsyncMock(
                return_value=self.test_ldap_id_mapping
            )
            self.microsoft_service.get_user_chats_by_user_id = AsyncMock(
                return_value=self.test_valided_chats_response
            )
            mock_pipeline = MagicMock()
            mock_pipeline.hset.return_value = None
            mock_pipeline.execute.return_value = None

            self.redis_client.pipeline.return_value = mock_pipeline

            result = await self.microsoft_meeting_chat_topic_cache_service.cache_chat_topics()

            self.assertEqual(result, self.test_chat_topics)
            self.microsoft_service.list_all_id_ldap_mapping.assert_called_once()
            self.microsoft_service.get_user_chats_by_user_id.assert_called_once()
            self.redis_client.pipeline.assert_called_once()
            mock_pipeline.hset.assert_called_once()
            mock_pipeline.execute.assert_called_once()


if __name__ == "__main__":
    main()
