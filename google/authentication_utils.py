from googleapiclient.discovery import build
from google.auth import default
from google.cloud.pubsub_v1 import SubscriberClient, PublisherClient
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from tools.log.logger import setup_logger
from tenacity import retry, stop_after_attempt, wait_exponential
from google.constants import (
    CHAT_API_NAME,
    CHAT_API_VERSION,
    PEOPLE_API_NAME,
    PEOPLE_API_VERSION,
    CREDENTIALS_SUCCESS_MSG,
    SERVICE_CREATED_MSG,
    IMPERSONATE_USER_MSG,
    USING_CREDENTIALS_MSG,
    USER_EMAIL,
    NO_CREDENTIALS_ERROR_MSG,
    SCOPES_LIST,
)
import logging
import os

setup_logger()


class GoogleClientFactory:
    """
    A singleton factory class for creating and managing Google API clients.

    This class ensures that only one instance of Google API clients (Chat and People) is created and shared
    across the application. It manages the retrieval of credentials and the creation of client instances,
    ensuring that they are initialized only once.

    Attributes:
        _instance (GoogleClientFactory): The singleton instance of the factory.
        _credentials (google.auth.credentials.Credentials): The retrieved Google Cloud credentials.
        _chat_client (googleapiclient.discovery.Resource): The created Google Chat API client instance.
        _people_client (googleapiclient.discovery.Resource): The created Google People API client instance.

    Methods:
        __new__(cls, *args, **kwargs): Creates or returns the singleton instance of the factory.
    """

    _instance = None
    _credentials = None
    _chat_client = None
    _people_client = None
    _subscriber_client = None
    _publisher_client = None
    _workspaceevents_client = None

    def __new__(cls, *args, **kwargs):
        """
        Creates or returns the singleton instance of the GoogleClientFactory.

        Args:
            cls (type): The class itself.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            GoogleClientFactory: The singleton instance.
        """

        if not cls._instance:
            cls._instance = super(GoogleClientFactory, cls).__new__(
                cls, *args, **kwargs
            )
        return cls._instance

    def _get_credentials(self):
        """Retrieves Google Cloud credentials using Application Default Credentials (ADC).

        This method fetches credentials via ADC, supporting both service account and user credentials.
        It caches the credentials to avoid redundant fetches and optionally impersonates a user if
        configured with a user email.

        Returns:
            google.auth.credentials.Credentials: The retrieved credentials object, or None if retrieval fails.

        Raises:
            google.auth.exceptions.DefaultCredentialsError: If ADC cannot locate valid credentials.
            Exception: For unexpected errors during credential retrieval or impersonation.
        """
        if self._credentials is not None:
            return self._credentials

        self._credentials, project_id = default(scopes=SCOPES_LIST)
        if not self._credentials:
            logging.error(NO_CREDENTIALS_ERROR_MSG)
            raise ValueError("No credentials found.")

        logging.info(CREDENTIALS_SUCCESS_MSG.format(project_id=project_id))

        user_email = os.environ.get(USER_EMAIL)

        if not user_email and isinstance(self._credentials, ServiceAccountCredentials):
            raise ValueError("Missing user email for service account impersonation.")

        if user_email and isinstance(self._credentials, ServiceAccountCredentials):
            self._credentials = self._credentials.with_subject(user_email)
            logging.info(IMPERSONATE_USER_MSG.format(user_email=user_email))

        logging.info(
            USING_CREDENTIALS_MSG.format(credentials_type=type(self._credentials))
        )

        return self._credentials

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=3),
    )
    def _create_client(self, api_name: str, api_version: str):
        """Creates a Google API client using Application Default Credentials (ADC).
        This function retrieves credentials using ADC and builds a Google API client.
        It includes automatic retry logic in case of failure (e.g., network issues, API rate limits).
        The method will retry up to 3 times with exponential backoff (waiting between 1 and 3 seconds before each retry).

        Args:
            api_name (str): The name of the API (e.g., "chat", "pubsub").
            api_version (str): The version of the API (e.g., "v1", "v1beta1").

        Returns:
            googleapiclient.discovery.Resource: The API client, or None if an error occurs after all retries.

        Raises:
            google.auth.exceptions.DefaultCredentialsError: If ADC fails to retrieve credentials.
            Exception: For any other unexpected errors during client creation.

        Example:
            chat_client = create_client("chat", "v1")
            if chat_client:
                # Use chat_client to interact with the Google Chat API
                pass
            else:
                print("Failed to create Chat client.")
        """

        credentials = self._get_credentials()
        if credentials is None:
            logging.error(NO_CREDENTIALS_ERROR_MSG)
            raise ValueError("Credentials are not available for creating the client.")
        service = build(api_name, api_version, credentials=credentials)
        if service is None:
            raise ValueError(f"Failed to create client for {api_name}.")
        logging.info(SERVICE_CREATED_MSG.format(api_name=api_name))
        return service

    def create_chat_client(self):
        """Creates a Google Chat API client.

        Returns:
            googleapiclient.discovery.Resource: The Google Chat API client, or None if an error occurs.
        """

        if self._chat_client is None:
            self._chat_client = self._create_client(CHAT_API_NAME, CHAT_API_VERSION)
        return self._chat_client

    def create_people_client(self):
        """Creates a Google People API client.
        Returns:
        googleapiclient.discovery.Resource: The Google People API client, or None if an error occurs.
        """

        if self._people_client is None:
            self._people_client = self._create_client(
                PEOPLE_API_NAME, PEOPLE_API_VERSION
            )
        return self._people_client

    def create_subscriber_client(self):
        """
        Creates a Google Cloud Pub/Sub subscriber client.

        Returns:
            pubsub_v1.SubscriberClient object if successful, else None.
        """

        if self._subscriber_client is None:
            self._subscriber_client = SubscriberClient()
        return self._subscriber_client

    def create_publisher_client(self):
        """
        Creates a Google Cloud Pub/Sub Publisher client.

        Returns:
            google.cloud.pubsub_v1.PublisherClient: The Publisher client instance.
        """

        if self._publisher_client is None:
            self._publisher_client = PublisherClient()
        return self._publisher_client

    def create_workspaceevents_client(self):
        """Creates a Google Workspace Events API client.

        This method initializes and returns a client for interacting with the Google Workspace Events API.
        If the client has not been created yet, it is instantiated using the `_create_client` method.

        Returns:
            googleapiclient.discovery.Resource: The Google Workspace Events API client instance.
        """

        if self._workspaceevents_client is None:
            self._workspaceevents_client = self._create_client("workspaceevents", "v1")
        return self._workspaceevents_client
