from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import patch, AsyncMock, Mock
from backend.historical_data.microsoft_ldap_fetcher import (
    get_all_microsoft_members,
    sync_microsoft_members_to_redis,
)
from backend.common.constants import MicrosoftAccountStatus


def make_mock_user(mail: str, display_name: str, account_enabled: bool) -> Mock:
    user = Mock()
    user.mail = mail
    user.display_name = display_name
    user.account_enabled = account_enabled
    return user


class TestMicrosoftLdapFetcher(IsolatedAsyncioTestCase):
    @patch(
        "backend.common.microsoft_client.MicrosoftClientFactory.create_graph_service_client"
    )
    async def test_get_all_microsoft_members_success(self, mock_create_client):
        member_active = make_mock_user("alice@circlecat.org", "Alice", True)
        member_terminated = make_mock_user("bob@circlecat.org", "Bob", False)

        mock_response = Mock()
        mock_response.value = [member_active, member_terminated]
        mock_users_client = AsyncMock()
        mock_users_client.users.get.return_value = mock_response
        mock_create_client.return_value = mock_users_client

        result = await get_all_microsoft_members()

        self.assertEqual(result, [member_active, member_terminated])
        mock_users_client.users.get.assert_awaited_once()

    @patch(
        "backend.common.microsoft_client.MicrosoftClientFactory.create_graph_service_client"
    )
    async def test_get_all_microsoft_members_client_none(self, mock_create_client):
        mock_create_client.return_value = None

        with self.assertRaises(ValueError):
            await get_all_microsoft_members()

    @patch(
        "backend.common.microsoft_client.MicrosoftClientFactory.create_graph_service_client"
    )
    async def test_get_all_microsoft_members_api_raises_exception(
        self, mock_create_client
    ):
        mock_client = AsyncMock()
        mock_client.users.get.side_effect = Exception("API error")
        mock_create_client.return_value = mock_client

        with self.assertRaises(RuntimeError):
            await get_all_microsoft_members()

        mock_client.users.get.assert_awaited_once()

    @patch(
        "backend.common.microsoft_client.MicrosoftClientFactory.create_graph_service_client"
    )
    async def test_get_all_microsoft_members_empty_result(self, mock_create_client):
        mock_response = Mock()
        mock_response.value = []
        mock_client = AsyncMock()
        mock_client.users.get.return_value = mock_response
        mock_create_client.return_value = mock_client

        result = await get_all_microsoft_members()

        self.assertEqual(result, [])
        mock_client.users.get.assert_awaited_once()

    @patch("backend.common.redis_client.RedisClientFactory.create_redis_client")
    @patch("backend.historical_data.microsoft_ldap_fetcher.get_all_microsoft_members")
    async def test_sync_microsoft_members_to_redis_success(
        self, mock_get_all_microsoft_members, mock_create_redis_client
    ):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis
        member_active = make_mock_user("alice@circlecat.org", "Alice", True)
        member_terminated = make_mock_user("bob@circlecat.org", "Bob", False)
        mock_get_all_microsoft_members.return_value = [member_active, member_terminated]

        mock_redis.hgetall.return_value = [{"alice": "AliceOld"}, {"bob": "Bob"}]
        mock_redis.hkeys.return_value = []

        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.hset = Mock()
        mock_pipeline.hdel = Mock()
        mock_pipeline.execute = Mock()

        result = await sync_microsoft_members_to_redis()

        mock_create_redis_client.assert_called_once()
        mock_get_all_microsoft_members.assert_awaited_once()

        mock_redis.hgetall.assert_called_once()
        mock_redis.hkeys.assert_called_once()

        mock_pipeline.hset.assert_any_call("ldap:active", "alice", "Alice")
        mock_pipeline.hset.assert_any_call("ldap:terminated", "bob", "Bob")
        mock_pipeline.hdel.assert_any_call("ldap:active", "bob")

        mock_pipeline.execute.assert_called_once()

        self.assertEqual(
            result,
            {
                MicrosoftAccountStatus.ACTIVE.value: 1,
                MicrosoftAccountStatus.TERMINATED.value: 1,
            },
        )

    @patch("backend.common.redis_client.RedisClientFactory.create_redis_client")
    async def test_sync_microsoft_members_to_redis_client_none(
        self, mock_create_redis_client
    ):
        mock_create_redis_client.return_value = None

        with self.assertRaises(ValueError):
            await sync_microsoft_members_to_redis()
        self.assertEqual(mock_create_redis_client.call_count, 3)

    @patch("backend.common.redis_client.RedisClientFactory.create_redis_client")
    @patch("backend.historical_data.microsoft_ldap_fetcher.get_all_microsoft_members")
    async def test_sync_microsoft_members_to_redis_get_members_exception(
        self, mock_get_all_microsoft_members, mock_create_redis_client
    ):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis
        mock_get_all_microsoft_members.side_effect = RuntimeError()

        with self.assertRaises(RuntimeError):
            await sync_microsoft_members_to_redis()

        self.assertEqual(mock_create_redis_client.call_count, 3)
        self.assertEqual(mock_get_all_microsoft_members.call_count, 3)
        mock_redis.delete.assert_not_called()
        mock_redis.hset.assert_not_called()

    @patch("backend.common.redis_client.RedisClientFactory.create_redis_client")
    @patch(
        "backend.historical_data.microsoft_ldap_fetcher.get_all_microsoft_members",
        new_callable=AsyncMock,
    )
    async def test_sync_microsoft_members_to_redis_redis_pipeline_execute_failure(
        self, mock_get_all_microsoft_members, mock_create_redis_client
    ):
        member_active = make_mock_user("alice@circlecat.org", "Alice", True)
        mock_get_all_microsoft_members.return_value = [member_active]

        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis

        mock_redis.hgetall.return_value = {}
        mock_redis.hkeys.return_value = []

        mock_pipeline = Mock()
        mock_pipeline.hset = Mock()
        mock_pipeline.hdel = Mock()
        mock_pipeline.execute.side_effect = Exception("Redis write error")
        mock_redis.pipeline.return_value = mock_pipeline

        with self.assertRaises(RuntimeError) as context:
            await sync_microsoft_members_to_redis()
        self.assertIn("Failed to update LDAP data in Redis", str(context.exception))

        self.assertEqual(mock_create_redis_client.call_count, 3)
        self.assertEqual(mock_get_all_microsoft_members.call_count, 3)
        self.assertEqual(mock_redis.pipeline.call_count, 3)
        self.assertEqual(mock_pipeline.execute.call_count, 3)


if __name__ == "__main__":
    main()
