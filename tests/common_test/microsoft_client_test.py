from functools import wraps
from unittest import TestCase, main
from unittest.mock import patch, Mock, call
from azure.identity import DefaultAzureCredential
from msgraph import GraphServiceClient
import os
from src.common.constants import MICROSOFT_SCOPES_LIST
from src.common.environment_constants import (
    AZURE_CLIENT_ID,
    AZURE_CLIENT_SECRET,
    AZURE_TENANT_ID,
)
from src.common.microsoft_client import MicrosoftClientFactory
from src.common.logger import get_logger

logger = get_logger()

TEST_AZURE_CLIENT_ID = "test-client-id"
TEST_AZURE_CLIENT_SECRET = "test-secret"
TEST_AZURE_TENANT_ID = "test-tenant"

ENV_VARS = {
    AZURE_CLIENT_ID: TEST_AZURE_CLIENT_ID,
    AZURE_CLIENT_SECRET: TEST_AZURE_CLIENT_SECRET,
    AZURE_TENANT_ID: TEST_AZURE_TENANT_ID,
}


class TestMicrosoftClientFactory(TestCase):
    def setUp(self):
        MicrosoftClientFactory._instance = None
        MicrosoftClientFactory._credentials = None
        MicrosoftClientFactory._graph_service_client = None

    @staticmethod
    def patch_microsoft_clients(test_func):
        @patch.dict(
            os.environ,
            {
                AZURE_CLIENT_ID: TEST_AZURE_CLIENT_ID,
                AZURE_CLIENT_SECRET: TEST_AZURE_CLIENT_SECRET,
                AZURE_TENANT_ID: TEST_AZURE_TENANT_ID,
            },
        )
        @patch("src.common.microsoft_client.DefaultAzureCredential")
        @patch("src.common.microsoft_client.GraphServiceClient")
        @wraps(test_func)
        def wrapper(
            mock_graph_service_client, mock_default_credential, *args, **kwargs
        ):
            return test_func(
                mock_graph_service_client, mock_default_credential, *args, **kwargs
            )

    @patch_microsoft_clients.__func__
    def test_create_graph_service_client_success(
        self, mock_graph_service_client, mock_default_credential
    ):
        mock_credentials = Mock(spec=DefaultAzureCredential)
        mock_default_credential.return_value = mock_credentials

        mock_graph_client = Mock(spec=GraphServiceClient)
        mock_graph_service_client.return_value = mock_graph_client

        factory = MicrosoftClientFactory()
        client1 = factory.create_graph_service_client()
        client2 = factory.create_graph_service_client()

        mock_default_credential.assert_called_once()
        mock_graph_service_client.assert_called_once_with(
            mock_credentials, MICROSOFT_SCOPES_LIST
        )
        self.assertIs(client1, mock_graph_client)
        self.assertIs(client2, mock_graph_client)

    @patch_microsoft_clients.__func__
    def test_create_graph_service_client_retries_on_failure(
        self, mock_graph_service_client, mock_default_credential
    ):
        mock_credentials = Mock(spec=DefaultAzureCredential)
        mock_default_credential.return_value = mock_credentials

        mock_graph_service_client.side_effect = [
            Exception,
            Mock(spec=GraphServiceClient),
        ]

        factory = MicrosoftClientFactory()
        client = factory.create_graph_service_client()

        self.assertEqual(mock_graph_service_client.call_count, 2)
        self.assertEqual(mock_default_credential.call_count, 2)
        self.assertIsInstance(client, GraphServiceClient)

    @patch_microsoft_clients.__func__
    def test_create_graph_service_client_failure(
        self, mock_graph_service_client, mock_default_credential
    ):
        mock_credentials = Mock(spec=DefaultAzureCredential)
        mock_default_credential.return_value = mock_credentials

        mock_graph_service_client.side_effect = [Exception, Exception, Exception]

        factory = MicrosoftClientFactory()

        with self.assertRaises(Exception):
            factory.create_graph_service_client()

        self.assertEqual(mock_graph_service_client.call_count, 3)
        self.assertEqual(mock_default_credential.call_count, 3)


if __name__ == "__main__":
    main()
