from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import patch, AsyncMock, Mock
from backend.historical_data.microsoft_ldap_fetcher import (
    get_all_microsoft_members,
)


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


if __name__ == "__main__":
    main()
