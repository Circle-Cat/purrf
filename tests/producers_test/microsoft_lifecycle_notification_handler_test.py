from http import HTTPStatus
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import patch, MagicMock, AsyncMock
from src.producers.microsoft_lifecycle_notification_handler.main import (
    _handle_lifecycle_notification_webhook,
    _init_graph_client,
    _init_redis_client,
    _validate_payload,
    _validate_identity,
    _renew_and_reauthorize_subscription,
    _process_lifecycle_event,
    MicrosoftLifecycleNotificationType,
    lifecycle_notification_webhook,
)

TEST_CLIENT_STATE = "secret1"
TEST_CLIENT_STATE2 = "secret2"
TEST_SUBSCRIPTION_ID = "sub1"
TEST_SUCCESS_PAYLOAD = [
    {
        "subscriptionId": TEST_SUBSCRIPTION_ID,
        "subscriptionExpirationDateTime": "2023-01-01T00:00:00Z",
        "tenantId": "tenant1",
        "clientState": TEST_CLIENT_STATE,
        "lifecycleEvent": MicrosoftLifecycleNotificationType.REAUTHORIZATION_REQUIRED,
    }
]
TEST_FAILED_PAYLOAD = [
    {
        "subscriptionId": "sub1",
        "subscriptionExpirationDateTime": "2023-01-01T00:00:00Z",
        "lifecycleEvent": "subscriptionRemoved",
    }
]

TEST_HANDSHAKE = {"validationToken": "test-validation-token"}
TEST_VALIDATE_NOTIFICATION = {"value": TEST_SUCCESS_PAYLOAD}


def make_request(args=None, json_data=None):
    request = MagicMock()
    request.args = args or {}
    request.get_json.return_value = json_data
    return request


class TestMicrosoftLifecycleNotificationHandler(IsolatedAsyncioTestCase):
    @patch("src.producers.microsoft_lifecycle_notification_handler.main.Redis")
    def test_init_redis_client_success(self, mock_redis):
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = None

        _init_redis_client()
        _init_redis_client()

        mock_redis.assert_called_once()
        mock_redis_instance.ping.assert_called_once()

    @patch("src.producers.microsoft_lifecycle_notification_handler.main.Redis")
    def test_init_redis_client_failure(self, mock_redis):
        mock_redis.side_effect = Exception()

        with self.assertRaises(Exception):
            _init_redis_client()

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main.GraphServiceClient"
    )
    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main.DefaultAzureCredential"
    )
    def test_init_graph_client_success(
        self, mock_deafult_credential, mock_graph_service
    ):
        mock_deafult_credential.return_value = MagicMock()
        mock_graph_service.return_value = MagicMock()

        _init_graph_client()
        _init_graph_client()

        mock_deafult_credential.assert_called_once()
        mock_graph_service.assert_called_once()

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main.GraphServiceClient"
    )
    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main.DefaultAzureCredential"
    )
    def test_init_graph_client_failure(
        self, mock_deafult_credential, mock_graph_service
    ):
        mock_deafult_credential.return_value = MagicMock()
        mock_graph_service.side_effect = Exception()

        with self.assertRaises(Exception):
            _init_graph_client()

    def test_validate_payload_success(self):
        self.assertTrue(_validate_payload(TEST_SUCCESS_PAYLOAD))

    def test_validate_payload_failure(self):
        self.assertFalse(_validate_payload(TEST_FAILED_PAYLOAD))

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main._init_redis_client"
    )
    @patch("src.producers.microsoft_lifecycle_notification_handler.main.redis_client")
    def test_validate_identity_success(self, mock_redis_client, mock_init_redis):
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [TEST_CLIENT_STATE]

        mock_redis_client.pipeline.return_value = mock_pipeline

        self.assertTrue(_validate_identity(TEST_SUCCESS_PAYLOAD))

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main._init_redis_client"
    )
    @patch("src.producers.microsoft_lifecycle_notification_handler.main.redis_client")
    def test_validate_identity_failure(self, mock_redis_client, mock_init_redis):
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [TEST_CLIENT_STATE2]

        mock_redis_client.pipeline.return_value = mock_pipeline

        self.assertFalse(_validate_identity(TEST_SUCCESS_PAYLOAD))

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main._init_graph_client"
    )
    @patch("src.producers.microsoft_lifecycle_notification_handler.main.graph_client")
    async def test_renew_and_reauthorize_subscription_success(
        self, mock_graph_client, mock_init_graph
    ):
        mock_patch_method = AsyncMock(return_value="result")
        mock_graph_client.subscriptions.by_subscription_id.return_value.patch = (
            mock_patch_method
        )

        result = await _renew_and_reauthorize_subscription(TEST_SUBSCRIPTION_ID)

        self.assertEqual(result, "result")

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main._init_graph_client"
    )
    @patch("src.producers.microsoft_lifecycle_notification_handler.main.graph_client")
    async def test_renew_and_reauthorize_subscription_failure(
        self, mock_graph_client, mock_init_graph
    ):
        mock_patch_method = AsyncMock()
        mock_patch_method.side_effect = Exception()
        mock_graph_client.subscriptions.by_subscription_id.return_value.patch = (
            mock_patch_method
        )

        with self.assertRaises(Exception):
            await _renew_and_reauthorize_subscription(TEST_SUBSCRIPTION_ID)

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main._renew_and_reauthorize_subscription",
        new_callable=AsyncMock,
    )
    async def test_process_lifecycle_event(self, mock_renew):
        mock_renew.return_value = "result"

        result = await _process_lifecycle_event(TEST_SUCCESS_PAYLOAD)

        self.assertTrue(result)
        mock_renew.assert_called_once()

    async def test_validation_token(self):
        request = make_request(args=TEST_HANDSHAKE)

        response, status = await _handle_lifecycle_notification_webhook(request)

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(response, "test-validation-token")

    async def test_none_json_body(self):
        request = make_request(json_data=None)

        response, status = await _handle_lifecycle_notification_webhook(request)

        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main._validate_identity",
        return_value=True,
    )
    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main._process_lifecycle_event",
        new_callable=AsyncMock,
    )
    async def test_successful_event(self, mock_process, mock_identity):
        mock_process.return_value = True

        request = make_request(json_data=TEST_VALIDATE_NOTIFICATION)

        response, status = await _handle_lifecycle_notification_webhook(request)

        self.assertEqual(status, HTTPStatus.OK)

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main._handle_lifecycle_notification_webhook",
        new_callable=AsyncMock,
    )
    def test_lifecycle_notification_webhook_success(self, mock_async_handler):
        mock_async_handler.return_value = "", HTTPStatus.OK

        request = make_request(json_data=TEST_VALIDATE_NOTIFICATION)

        response_body, status_code = lifecycle_notification_webhook(request)

        self.assertEqual(status_code, HTTPStatus.OK)
        mock_async_handler.assert_awaited_once()

    @patch(
        "src.producers.microsoft_lifecycle_notification_handler.main._handle_lifecycle_notification_webhook",
        new_callable=AsyncMock,
    )
    def test_lifecycle_notification_webhook_sync_wrapper_async_error(
        self, mock_async_handler
    ):
        mock_async_handler.return_value = "", HTTPStatus.INTERNAL_SERVER_ERROR

        request = make_request(json_data=TEST_VALIDATE_NOTIFICATION)

        response_body, status_code = lifecycle_notification_webhook(request)

        self.assertEqual(status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        mock_async_handler.assert_awaited_once()


if __name__ == "__main__":
    main()
