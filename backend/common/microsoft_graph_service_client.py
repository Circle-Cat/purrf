from azure.identity import DefaultAzureCredential
from msgraph import GraphServiceClient
from backend.common.constants import MICROSOFT_SCOPES_LIST


class MicrosoftGraphServiceClient:
    """
    A wrapper for the Microsoft GraphServiceClient.
    This class initializes and exposes a Microsoft Graph SDK client instance
    using Azure's DefaultAzureCredential for authentication. It is intended
    to be instantiated once and reused across the application.
    Example:
        service_client = MicrosoftGraphServiceClient()
        graph_client = service_client.get_graph_service_client
    """

    def __init__(self):
        """
        Initializes the Microsoft GraphServiceClient with Azure credentials and scopes.
        Uses DefaultAzureCredential for authentication, which supports various environments.
        The Microsoft Graph client is created immediately when this class is instantiated.
        """
        self._graph_service_client = GraphServiceClient(
            DefaultAzureCredential(), MICROSOFT_SCOPES_LIST
        )

    @property
    def get_graph_service_client(self) -> GraphServiceClient:
        """
        Returns the initialized Microsoft Graph service client.
        Returns:
            GraphServiceClient: The Microsoft Graph client instance.
        """
        return self._graph_service_client
