from azure.identity import DefaultAzureCredential
from msgraph import GraphServiceClient
from backend.common.constants import MICROSOFT_SCOPES_LIST
from backend.common.logger import get_logger
from tenacity import retry, stop_after_attempt, wait_exponential

logger = get_logger()


# TODO: Delete this class after migrating all Microsoft-related functionality.
class MicrosoftClientFactory:
    """
    A singleton factory class for managing asynchronous Azure credentials and creating Microsoft Graph API clients.

    This class ensures that a single instance of Azure credentials (`DefaultAzureCredential`) is created and shared
    across the application to acquire access tokens for Microsoft Graph API interactions, such as subscribing to
    Teams chat message notifications. Each call to `create_graph_service_client` creates a new `GraphServiceClient`
    instance using the cached credentials, allowing flexibility in client usage while minimizing credential initialization overhead.

    Attributes:
        _instance (MicrosoftClientFactory): The singleton instance of the factory.
        _credentials (azure.identity.aio.DefaultAzureCredential): Cached asynchronous Azure credentials for token acquisition.
        _graph_service_client (msgraph.GraphServiceClient): The Microsoft Graph API client instance.

    Methods:
        __new__(cls, *args, **kwargs): Creates or returns the singleton instance of the factory.
        _get_credentials(self): Retrieves and caches asynchronous Azure credentials.
        create_graph_service_client(self): Creates a new Microsoft Graph API client using cached credentials.
    """

    _instance = None
    _credentials = None
    _graph_service_client = None

    def __new__(cls, *args, **kwargs):
        """
        Creates or returns the singleton instance of the MicrosoftClientFactory.

        Args:
            cls (type): The class itself.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            MicrosoftClientFactory: The singleton instance.
        """

        if not cls._instance:
            cls._instance = super(MicrosoftClientFactory, cls).__new__(
                cls, *args, **kwargs
            )
        return cls._instance

    def _get_credentials(self):
        """
        Retrieves and caches Azure credentials using DefaultAzureCredential.

        This method uses the DefaultAzureCredential class from the Azure SDK to fetch credentials.
        If the credentials have not been cached yet, it will retrieve and cache them.

        Returns:
            azure.identity.Credentials: The retrieved credentials object.

        Raises:
            azure.core.exceptions.AuthenticationError: If the credentials are invalid or the authentication fails.
            Exception: If there are any unexpected errors during the credential retrieval or impersonation process.
        """
        if self._credentials:
            return self._credentials

        self._credentials = DefaultAzureCredential()
        logger.info(f"Using Credentials type: {type(self._credentials)}")
        return self._credentials

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=3),
    )
    def create_graph_service_client(self):
        """
        Creates and returns a new asynchronous Microsoft Graph API client using the cached credentials.

        This method constructs a new `GraphServiceClient` instance for interacting with Microsoft Graph API
        endpoints, such as subscribing to Teams chat message notifications. It uses cached Azure credentials
        and predefined scopes from `MICROSOFT_SCOPES_LIST`. The method is decorated with a retry mechanism
        to handle transient failures.

        Returns:
            msgraph.GraphServiceClient: The Microsoft Graph API client instance.
        """
        scopes = MICROSOFT_SCOPES_LIST
        try:
            self._graph_service_client = GraphServiceClient(
                self._get_credentials(), scopes
            )
            logger.debug("Created new GraphServiceClient instance")
        except Exception:
            self._credentials = None
            raise
        return self._graph_service_client
