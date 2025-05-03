from google.auth.impersonated_credentials import Credentials as ImpersonatedCredentials
from google.cloud.pubsub_v1 import SubscriberClient, PublisherClient
from googleapiclient.discovery import build
from google.auth import default
from tenacity import retry, stop_after_attempt, wait_exponential
from src.common.environment_constants import USER_EMAIL, SERVICE_ACCOUNT_EMAIL
from src.common.constants import GOOGLE_SCOPES_LIST
from src.common.logger import get_logger
import os

logger = get_logger()


class GoogleClientFactory:
    """
    A singleton factory class for creating and managing Google API clients.

    This class ensures that only one instance of Google API clients (Chat, People, Workspace Events,
    Pub/Sub Publisher and Subscriber) is created and shared across the application. It manages the
    retrieval of credentials and the creation of client instances, ensuring they are initialized only once.

    Attributes:
        _instance (GoogleClientFactory): The singleton instance of the factory.
        _credentials (google.auth.credentials.Credentials): The retrieved Google Cloud credentials.
        _chat_client (googleapiclient.discovery.Resource): The created Google Chat API client instance.
        _people_client (googleapiclient.discovery.Resource): The created Google People API client instance.
        _workspaceevents_client (googleapiclient.discovery.Resource): The created Google Workspace Events API client.
        _subscriber_client (google.cloud.pubsub_v1.SubscriberClient): The created Pub/Sub Subscriber client instance.
        _publisher_client (google.cloud.pubsub_v1.PublisherClient): The created Pub/Sub Publisher client instance.
    """

    _instance = None
    _credentials = None
    _chat_client = None
    _people_client = None
    _workspaceevents_client = None
    _subscriber_client = None
    _publisher_client = None

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

    def _get_impersonate_credentials(self):
        """Retrieves and caches Google Cloud credentials with impersonation using ADC.

        This method fetches credentials via ADC, and impersonates a user if a user email is provided,
        using a target service account.

        Returns:
            google.auth.credentials.Credentials: The retrieved credentials object.

        Raises:
            ValueError: If any required configuration (user email, service account email) is missing.
            google.auth.exceptions.DefaultCredentialsError: If ADC cannot locate valid credentials.
            ValueError: If user impersonation fails.
            Exception: For unexpected errors during credential retrieval or impersonation.
        """
        if self._credentials:
            logger.info("Credentials are already cached.")
            return self._credentials

        user_email = os.environ.get(USER_EMAIL)
        service_account_email = os.environ.get(SERVICE_ACCOUNT_EMAIL)
        if not user_email:
            logger.error(
                f"Impersonation failed: environment variable {USER_EMAIL} is not set."
            )
            raise ValueError(f"Please set environment variable: {USER_EMAIL}.")

        if not service_account_email:
            logger.error(
                f"Impersonation failed: environment variable {SERVICE_ACCOUNT_EMAIL} is not set."
            )
            raise ValueError(
                f"Please set environment variable: {SERVICE_ACCOUNT_EMAIL}."
            )

        self._credentials, project_id = default()
        if not self._credentials:
            logger.error(
                "Failed to obtain ADC credentials: no valid default credentials found."
            )
            raise ValueError("Google authentication service unavailable.")

        credentials_type = type(self._credentials)
        logger.info(
            f"Credentials retrieved successfully. Project ID: {project_id}. Credentials type: {credentials_type}"
        )

        try:
            self._credentials = ImpersonatedCredentials(
                source_credentials=self._credentials,
                target_principal=service_account_email,
                target_scopes=GOOGLE_SCOPES_LIST,
                subject=user_email,
            )

            logger.info(
                f"Successfully impersonated user: {user_email} using service account: {service_account_email}"
            )

        except Exception as e:
            original_error = str(e)
            logger.error(
                f"Impersonation failed with original error: {original_error}",
                exc_info=True,
            )
            logger.error(
                f"Impersonation troubleshooting details:\n"
                f"1. User email ('{user_email}') may be invalid or not in the Google Workspace domain.\n"
                f"2. Target service account ('{service_account_email}') may not have domain-wide delegation enabled.\n"
                f"3. Source credentials (from gcloud auth application-default login) may lack 'roles/iam.serviceAccountTokenCreator' role on the target service account.\n"
                f"   To fix, contact admin to grant your account this role.\n"
                f"4. IAM Credentials API may not be enabled (run: gcloud services enable iamcredentials.googleapis.com).\n"
                f"5. OAuth scopes ({GOOGLE_SCOPES_LIST}) may not be authorized for domain-wide delegation.\n"
                f"For more details, refer to: https://cloud.google.com/iam/docs/service-account-impersonation"
            )
            raise ValueError(
                "Authentication failed. Please contact support for assistance."
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

        credentials = self._get_impersonate_credentials()
        if not credentials:
            raise ValueError("Credentials are not available for creating the client.")
        service = build(api_name, api_version, credentials=credentials)
        if not service:
            raise ValueError(f"Failed to create client for {api_name}.")
        logger.info(f"Created {api_name} client successfully.")
        return service

    def create_chat_client(self):
        """Creates a Google Chat API client.

        Returns:
            googleapiclient.discovery.Resource: The Google Chat API client, or None if an error occurs.
        """

        if not self._chat_client:
            self._chat_client = self._create_client("chat", "v1")
        return self._chat_client

    def create_people_client(self):
        """Creates a Google People API client.
        Returns:
        googleapiclient.discovery.Resource: The Google People API client, or None if an error occurs.
        """

        if not self._people_client:
            self._people_client = self._create_client("people", "v1")
        return self._people_client

    def create_workspaceevents_client(self):
        """Creates a Google Workspace Events API client.

        This method initializes and returns a client for interacting with the Google Workspace Events API.
        If the client has not been created yet, it is instantiated using the `_create_client` method.

        Returns:
            googleapiclient.discovery.Resource: The Google Workspace Events API client instance.
        """

        if not self._workspaceevents_client:
            self._workspaceevents_client = self._create_client("workspaceevents", "v1")
        return self._workspaceevents_client

    def create_subscriber_client(self):
        """
        Creates a Google Cloud Pub/Sub subscriber client.

        Returns:
            pubsub_v1.SubscriberClient object if successful, else None.
        """

        if not self._subscriber_client:
            self._subscriber_client = SubscriberClient()
        return self._subscriber_client

    def create_publisher_client(self):
        """
        Creates a Google Cloud Pub/Sub Publisher client.

        Returns:
            google.cloud.pubsub_v1.PublisherClient: The Publisher client instance.
        """

        if not self._publisher_client:
            self._publisher_client = PublisherClient()
        return self._publisher_client
