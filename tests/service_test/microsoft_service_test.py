from http import HTTPStatus

from unittest import main, IsolatedAsyncioTestCase
from unittest.mock import MagicMock, AsyncMock, ANY
from src.service.microsoft_service import MicrosoftService


def make_mock_user(mail, display_name, account_enabled, user_id=None):
    mock_user = MagicMock()
    mock_user.mail = mail
    mock_user.display_name = display_name
    mock_user.account_enabled = account_enabled
    mock_user.id = user_id
    return mock_user


class TestMicrosoftService(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_graph_client = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.service = MicrosoftService(
            self.mock_logger, self.mock_graph_client, self.mock_retry_utils
        )
        self.chat_id = "test_chat_id"
        self.url = "https://graph.microsoft.com/v1.0/chats/some_chat_id/messages?$skiptoken=abc"
        self.user_id = "test_user_id"
        self.ldap = "alice"
        self.user_mail = "alice@circlecat.org"
        self.message_id = "test_message_id"

    async def test_get_all_microsoft_members_success(self):
        member_active = make_mock_user("alice@circlecat.org", "Alice", True)
        member_terminated = make_mock_user("bob@circlecat.org", "Bob", False)

        mock_response = MagicMock()
        mock_response.value = [member_active, member_terminated]

        mock_get_retry_on_transient = AsyncMock(return_value=mock_response)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.get_all_microsoft_members()

        self.assertEqual(result, [member_active, member_terminated])
        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.users.get, request_configuration=ANY
        )

    async def test_get_all_microsoft_members_empty_result(self):
        mock_response = MagicMock()
        mock_response.value = []

        mock_get_retry_on_transient = AsyncMock(return_value=mock_response)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.get_all_microsoft_members()

        self.assertEqual(result, [])
        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.users.get, request_configuration=ANY
        )

    async def test_fetch_initial_chat_messages_page_success(self):
        mock_response = MagicMock()
        mock_get_retry_on_transient = AsyncMock(return_value=mock_response)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.fetch_initial_chat_messages_page(self.chat_id)

        self.assertEqual(result, mock_response)
        self.mock_retry_utils.get_retry_on_transient.assert_awaited_once_with(
            self.mock_graph_client.chats.by_chat_id(self.chat_id).messages.get,
            request_configuration=ANY,
        )

    async def test_fetch_initial_chat_messages_page_no_chat_id(self):
        with self.assertRaises(ValueError):
            await self.service.fetch_initial_chat_messages_page("")

    async def test_fetch_chat_messages_by_url_success(self):
        mock_response = MagicMock()
        mock_get_retry_on_transient = AsyncMock(return_value=mock_response)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.fetch_chat_messages_by_url(self.chat_id, self.url)

        self.assertEqual(result, mock_response)
        self.mock_retry_utils.get_retry_on_transient.assert_awaited_once_with(
            self.mock_graph_client.chats.by_chat_id(self.chat_id)
            .messages.with_url(self.url)
            .get
        )

    async def test_fetch_chat_messages_by_url_no_chat_id(self):
        with self.assertRaises(ValueError):
            await self.service.fetch_chat_messages_by_url("", self.url)

    async def test_fetch_chat_messages_by_url_no_url(self):
        with self.assertRaises(ValueError):
            await self.service.fetch_chat_messages_by_url(self.chat_id, "")

    async def test_get_ldap_by_id_success(self):
        mock_user = MagicMock()
        mock_user.mail = self.user_mail
        mock_get_retry_on_transient = AsyncMock(return_value=mock_user)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.get_ldap_by_id(self.user_id)

        self.assertEqual(result, self.ldap)
        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.users.by_user_id(self.user_id).get
        )

    async def test_get_ldap_by_id_user_not_found(self):
        not_found_exception = Exception("User not found")
        setattr(not_found_exception, "response_status_code", HTTPStatus.NOT_FOUND)

        mock_get_retry_on_transient = AsyncMock(side_effect=not_found_exception)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.get_ldap_by_id(self.user_id)

        self.assertIsNone(result)
        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.users.by_user_id(self.user_id).get
        )

    async def test_get_ldap_by_id_invalid_mail_format(self):
        mock_user = MagicMock()
        mock_user.mail = "invalid-email-without-at"
        mock_get_retry_on_transient = AsyncMock(return_value=mock_user)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.get_ldap_by_id(self.user_id)

        self.assertIsNone(result)
        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.users.by_user_id(self.user_id).get
        )

    async def test_get_message_by_id_success(self):
        mock_message = MagicMock()
        mock_get_retry_on_transient = AsyncMock(return_value=mock_message)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.get_message_by_id(self.chat_id, self.message_id)

        self.assertEqual(result, mock_message)
        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.chats.by_chat_id(self.chat_id)
            .messages.by_chat_message_id(self.message_id)
            .get
        )

    async def test_get_message_by_id_no_chat_id(self):
        with self.assertRaises(ValueError):
            await self.service.get_message_by_id("", self.message_id)

        self.mock_retry_utils.get_retry_on_transient.assert_not_called()

    async def test_get_message_by_id_no_message_id(self):
        with self.assertRaises(ValueError):
            await self.service.get_message_by_id(self.chat_id, "")

        self.mock_retry_utils.get_retry_on_transient.assert_not_called()

    async def test_list_all_id_ldap_mapping_success(self):
        member_active = make_mock_user("alice@circlecat.org", "Alice", True, "id_1")
        member_terminated = make_mock_user("bob@circlecat.org", "Bob", False, "id_2")

        mock_response = [member_active, member_terminated]

        self.service.get_all_microsoft_members = AsyncMock(return_value=mock_response)

        result = await self.service.list_all_id_ldap_mapping()

        self.assertEqual(result, {"id_1": "alice", "id_2": "bob"})
        self.service.get_all_microsoft_members.assert_awaited_once()

    async def test_get_user_chats_by_user_id_success(self):
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.value = [mock_chat]

        mock_get_retry_on_transient = AsyncMock(return_value=mock_response)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.get_user_chats_by_user_id(self.user_id)

        self.assertEqual(result, [mock_chat])
        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.users.by_user_id(self.user_id).chats.get
        )

    async def test_get_user_chats_by_user_id_raises_on_empty_user_id(self):
        with self.assertRaises(ValueError):
            await self.service.get_user_chats_by_user_id("")
        self.mock_retry_utils.get_retry_on_transient.assert_not_called()

    async def test_list_all_subscriptions_success(self):
        mock_subscription = MagicMock()
        mock_response = MagicMock()
        mock_response.value = [mock_subscription]

        mock_get_retry_on_transient = AsyncMock(return_value=mock_response)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.list_all_subscriptions()

        self.assertEqual(result, [mock_subscription])
        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.subscriptions.get
        )

    async def test_delete_subscription_success(self):
        mock_get_retry_on_transient = AsyncMock()
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        await self.service.delete_subscription("sub-id-123")

        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.subscriptions.by_subscription_id(
                "sub-id-123"
            ).delete
        )

    async def test_create_subscription_success(self):
        mock_subscription = MagicMock()
        mock_get_retry_on_transient = AsyncMock(return_value=mock_subscription)
        self.service.retry_utils.get_retry_on_transient = mock_get_retry_on_transient

        result = await self.service.create_subscription(
            change_type="created,updated",
            notification_url="https://callback.example.com/notify",
            lifecycle_notification_url="https://callback.example.com/lifecycle",
            resource="chats",
            expiration_date_time="2025-12-31T23:59:59Z",
            client_state="random_client_state_123",
        )

        self.assertEqual(result, mock_subscription)
        mock_get_retry_on_transient.assert_awaited_once_with(
            self.service.graph_service_client.subscriptions.post, ANY
        )


if __name__ == "__main__":
    main()
