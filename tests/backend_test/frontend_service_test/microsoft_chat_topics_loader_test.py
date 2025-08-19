import os
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import patch, AsyncMock, MagicMock

from msgraph.generated.models.chat import Chat
from msgraph.generated.models.chat_type import ChatType
from msgraph.generated.models.teamwork_online_meeting_info import (
    TeamworkOnlineMeetingInfo,
)
from msgraph.generated.models.teamwork_user_identity import TeamworkUserIdentity
from msgraph.generated.models.chat_collection_response import ChatCollectionResponse

from backend.frontend_service.microsoft_chat_topics_loader import (
    get_microsoft_chat_topics,
    cache_chat_topics,
)
from backend.common.environment_constants import (
    MICROSOFT_ADMIN_LDAP,
    MICROSOFT_USER_LDAP,
)


class TestMicrosoftChatTopicsLoader(IsolatedAsyncioTestCase):
    TEST_CHAT_TOPICS = {
        "chat_id_1": "Topic 1",
    }
    TEST_USER_LDAP = "user"
    TEST_ADMIN_LDAP = "admin"
    TEST_LDAP_ID_MAPPING = {"id_1": TEST_USER_LDAP, "id_2": TEST_ADMIN_LDAP}

    TEST_NO_CHATS_RESPONSE = ChatCollectionResponse(value=[])

    TEST_VALIDED_CHATS_RESPONSE = ChatCollectionResponse(
        value=[
            Chat(
                id="chat_id_1",
                topic="Topic 1",
                chat_type=ChatType.Meeting,
                online_meeting_info=TeamworkOnlineMeetingInfo(
                    organizer=TeamworkUserIdentity(id="id_2")
                ),
            )
        ]
    )

    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.RedisClientFactory.create_redis_client"
    )
    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.cache_chat_topics",
        new_callable=AsyncMock,
    )
    async def test_get_microsoft_chat_topics_cache_hit(
        self, mock_cache_chat_topics, mock_redis_client
    ):
        mock_client = MagicMock()
        mock_client.hgetall.return_value = self.TEST_CHAT_TOPICS
        mock_redis_client.return_value = mock_client

        result = await get_microsoft_chat_topics()

        mock_client.hgetall.assert_called_once()
        self.assertEqual(result, self.TEST_CHAT_TOPICS)

    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.RedisClientFactory.create_redis_client"
    )
    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.cache_chat_topics",
        new_callable=AsyncMock,
    )
    async def test_get_microsoft_chat_topics_cache_miss(
        self, mock_cache_chat_topics, mock_redis_client
    ):
        mock_client = MagicMock()
        mock_client.hgetall.return_value = None
        mock_redis_client.return_value = mock_client

        mock_cache_chat_topics.return_value = self.TEST_CHAT_TOPICS

        result = await get_microsoft_chat_topics()

        mock_client.hgetall.assert_called_once()
        mock_cache_chat_topics.assert_called_once()
        self.assertEqual(result, self.TEST_CHAT_TOPICS)

    async def test_cache_chat_topics_missing_env_vars(self):
        mock_redis_client = MagicMock()
        with self.assertRaises(ValueError):
            await cache_chat_topics(mock_redis_client)

    @patch.dict(
        os.environ,
        {MICROSOFT_ADMIN_LDAP: "invalided_user", MICROSOFT_USER_LDAP: TEST_USER_LDAP},
    )
    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.MicrosoftClientFactory.create_graph_service_client"
    )
    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.list_all_id_ldap_mapping",
        new_callable=AsyncMock,
    )
    async def test_cache_chat_topics_invalided_ldap(
        self, mock_list_all_id_ldap_mapping, mock_graph_client
    ):
        mock_redis_client = MagicMock()
        mock_list_all_id_ldap_mapping.return_value = self.TEST_LDAP_ID_MAPPING

        with self.assertRaises(ValueError):
            await cache_chat_topics(mock_redis_client)

        mock_list_all_id_ldap_mapping.assert_called_once()
        mock_redis_client.assert_not_called()
        mock_graph_client.assert_not_called()

    @patch.dict(
        os.environ,
        {MICROSOFT_ADMIN_LDAP: TEST_ADMIN_LDAP, MICROSOFT_USER_LDAP: TEST_USER_LDAP},
    )
    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.MicrosoftClientFactory"
    )
    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.list_all_id_ldap_mapping",
        new_callable=AsyncMock,
    )
    async def test_cache_chat_topics_no_chats(
        self, mock_list_all_id_ldap_mapping, mock_graph_factory
    ):
        mock_redis_client = MagicMock()
        mock_list_all_id_ldap_mapping.return_value = self.TEST_LDAP_ID_MAPPING

        mock_get = AsyncMock(return_value=self.TEST_NO_CHATS_RESPONSE)
        mock_chats = MagicMock()
        mock_chats.get = mock_get
        mock_user_object = MagicMock(chats=mock_chats)
        mock_users = MagicMock(by_user_id=MagicMock(return_value=mock_user_object))
        mock_graph_client = MagicMock(users=mock_users)
        mock_graph_factory.return_value.create_graph_service_client.return_value = (
            mock_graph_client
        )

        with self.assertRaises(ValueError):
            await cache_chat_topics(mock_redis_client)

        mock_list_all_id_ldap_mapping.assert_called_once()
        mock_get.assert_called_once()
        mock_redis_client.assert_not_called()

    @patch.dict(
        os.environ,
        {MICROSOFT_ADMIN_LDAP: TEST_ADMIN_LDAP, MICROSOFT_USER_LDAP: TEST_USER_LDAP},
    )
    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.MicrosoftClientFactory"
    )
    @patch(
        "backend.frontend_service.microsoft_chat_topics_loader.list_all_id_ldap_mapping",
        new_callable=AsyncMock,
    )
    async def test_cache_chat_topics_success(
        self, mock_list_all_id_ldap_mapping, mock_graph_factory
    ):
        mock_pipeline = MagicMock()
        mock_redis_client = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline

        mock_list_all_id_ldap_mapping.return_value = self.TEST_LDAP_ID_MAPPING

        mock_get = AsyncMock(return_value=self.TEST_VALIDED_CHATS_RESPONSE)
        mock_chats = MagicMock()
        mock_chats.get = mock_get
        mock_user_object = MagicMock(chats=mock_chats)
        mock_users = MagicMock(by_user_id=MagicMock(return_value=mock_user_object))
        mock_graph_client = MagicMock(users=mock_users)
        mock_graph_factory.return_value.create_graph_service_client.return_value = (
            mock_graph_client
        )

        result = await cache_chat_topics(mock_redis_client)

        self.assertEqual(result, self.TEST_CHAT_TOPICS)
        mock_list_all_id_ldap_mapping.assert_called_once()
        mock_get.assert_called_once()
        mock_pipeline.hset.assert_called_once()
        mock_pipeline.execute.assert_called_once()


if __name__ == "__main__":
    main()
