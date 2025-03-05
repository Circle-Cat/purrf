from googleapiclient.discovery import build
from google.auth import default
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from tools.log.logger import setup_logger
from google.constants import (
    CHAT_API_NAME,
    CHAT_API_VERSION,
    PEOPLE_API_NAME,
    PEOPLE_API_VERSION,
    CREDENTIALS_SUCCESS_MSG,
    USING_SERVICE_ACCOUNT_CREDENTIALS_MSG,
    USING_USER_CREDENTIALS_MSG,
    USING_OTHER_CREDENTIALS_MSG,
    NO_CREDENTIALS_ERROR_MSG,
    SERVICE_CREATED_MSG,
)
import logging

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

        This function attempts to retrieve credentials using ADC. It supports both service account
        and user credentials.

        Returns:
            google.auth.credentials.Credentials: The retrieved credentials object, or None.
        Raises:
            google.auth.exceptions.DefaultCredentialsError: If ADC fails to retrieve credentials.
            Exception: For any other unexpected errors during credential retrieval or delegation.

        Example:
            credentials = get_credentials()
            if credentials:
                # Use credentials to access Google Cloud services
                pass
            else:
                print("Failed to retrieve credentials.")
        """

        if self._credentials is None:
            self._credentials, project_id = default()
            logging.info(CREDENTIALS_SUCCESS_MSG.format(project_id=project_id))
            if isinstance(self._credentials, ServiceAccountCredentials):
                logging.info(USING_SERVICE_ACCOUNT_CREDENTIALS_MSG)
            elif isinstance(self._credentials, UserCredentials):
                logging.info(USING_USER_CREDENTIALS_MSG)
            else:
                logging.info(
                    USING_OTHER_CREDENTIALS_MSG.format(
                        credentials_type=type(self._credentials)
                    )
                )
        return self._credentials

    def _create_client(self, api_name: str, api_version: str):
        """Creates a Google API client using Application Default Credentials (ADC).
        This function retrieves credentials using ADC and builds a Google API client.

        Args:
            api_name (str): The name of the API (e.g., "chat", "pubsub").
            api_version (str): The version of the API (e.g., "v1", "v1beta1").

        Returns:
            googleapiclient.discovery.Resource: The API client, or None if an error occurs.

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
            return None
        service = build(api_name, api_version, credentials=credentials)
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
