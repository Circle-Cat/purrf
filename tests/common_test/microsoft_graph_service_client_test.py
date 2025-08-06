import unittest
from unittest.mock import patch, MagicMock
from src.common.microsoft_graph_service_client import MicrosoftGraphServiceClient


class TestMicrosoftGraphServiceClient(unittest.TestCase):
    @patch("src.common.microsoft_graph_service_client.GraphServiceClient")
    @patch("src.common.microsoft_graph_service_client.DefaultAzureCredential")
    @patch(
        "src.common.microsoft_graph_service_client.MICROSOFT_SCOPES_LIST",
        ["https://graph.microsoft.com/.default"],
    )
    def test_initialization(self, mock_credential_class, mock_graph_client_class):
        mock_credential_instance = MagicMock()
        mock_credential_class.return_value = mock_credential_instance
        mock_graph_client_instance = MagicMock()
        mock_graph_client_class.return_value = mock_graph_client_instance

        client = MicrosoftGraphServiceClient()

        mock_credential_class.assert_called_once()
        mock_graph_client_class.assert_called_once_with(
            mock_credential_instance, ["https://graph.microsoft.com/.default"]
        )
        self.assertEqual(client.get_graph_service_client, mock_graph_client_instance)


if __name__ == "__main__":
    unittest.main()
