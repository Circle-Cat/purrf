from google.auth.impersonated_credentials import Credentials as ImpersonatedCredentials
from google.cloud.pubsub_v1 import SubscriberClient, PublisherClient
from googleapiclient.discovery import build
from google.apps import meet_v2
from google.auth import default
from backend.common.constants import GOOGLE_USER_SCOPES_LIST, GOOGLE_ADMIN_SCOPES_LIST
from backend.common.environment_constants import (
    USER_EMAIL,
    SERVICE_ACCOUNT_EMAIL,
    ADMIN_EMAIL,
)
import os
import threading


class _ThreadLocalResource:
    """A Google API resource that resolves to one service per calling thread.

    A ``googleapiclient`` service owns a single ``httplib2`` connection, and
    httplib2 requires one instance per thread: threads sharing a service write
    into the same socket and read each other's replies. These resources are
    held as process-wide singletons and reached from worker threads through
    ``asyncio.to_thread``, so the resource resolves a service on each attribute
    access instead of closing over one.

    Attribute access is the entire surface callers use --- ``events()``,
    ``people()``, ``new_batch_http_request()`` --- so forwarding it covers every
    call. A request object built through this resource belongs to the thread
    that built it and must be executed on that thread.
    """

    def __init__(self, build_service):
        """Wraps a service factory and resolves a service for the caller.

        Resolving here means a broken configuration still fails when the
        resource is created rather than on a later call.

        Args:
            build_service (Callable[[], googleapiclient.discovery.Resource]):
                Builds a service for one thread.
        """
        self._build_service = build_service
        self._local = threading.local()
        self._resolve()

    def _resolve(self):
        """Returns the calling thread's service, building it on first use.

        Returns:
            googleapiclient.discovery.Resource: The calling thread's service.
        """
        service = getattr(self._local, "service", None)
        if service is None:
            service = self._build_service()
            self._local.service = service
        return service

    def __getattr__(self, name):
        return getattr(self._resolve(), name)


class GoogleClient:
    """
    A class for creating and managing Google API clients.

    This class manages the creation of Google API clients such as:
      - Chat, People, Workspace Events, Calendar, and Admin Reports (via googleapiclient)
      - Pub/Sub Publisher and Subscriber (via google.cloud.pubsub_v1)

    It uses Application Default Credentials (ADC) and impersonation of a target service account
    to obtain user-scoped credentials. Credentials and client creation can be retried using
    an injected `retry_utils` helper that handles transient errors.

    Attributes:
        _credentials (dict[str, google.auth.credentials.Credentials]): Impersonated credentials keyed by user email, cached per calling thread.
        _user_email (str): The user email to impersonate by default.
        _service_account_email (str): The target service account used for impersonation.
        _admin_email (str): Admin user email for domain-wide delegated APIs (e.g. Reports API).
        logger: Application logger for structured logging.
        retry_utils: Utility providing `get_retry_on_transient(func)` for automatic retries.
    """

    def __init__(
        self,
        logger,
        retry_utils,
    ):
        self._local = threading.local()
        self._user_email = os.getenv(USER_EMAIL)
        self._service_account_email = os.getenv(SERVICE_ACCOUNT_EMAIL)
        self._admin_email = os.getenv(ADMIN_EMAIL)
        self.logger = logger
        self.retry_utils = retry_utils

        if not self._user_email:
            raise ValueError("Missing environment variable: USER_EMAIL")
        if not self._service_account_email:
            raise ValueError("Missing environment variable: SERVICE_ACCOUNT_EMAIL")
        if not self._admin_email:
            raise ValueError("Missing environment variable: ADMIN_EMAIL")
        if not self.logger:
            raise ValueError("logger must be provided")
        if not self.retry_utils:
            raise ValueError("retry_utils must be provided")

    @property
    def _credentials(self):
        """Returns the calling thread's cache of impersonated credentials.

        A ``Credentials`` object holds a mutable access token and its expiry,
        so threads refreshing one shared instance race on it. Each thread keeps
        its own cache and pays one token exchange per email per hour.

        Returns:
            dict[str, google.auth.credentials.Credentials]: Credentials keyed by user email.
        """
        cache = getattr(self._local, "credentials", None)
        if cache is None:
            cache = {}
            self._local.credentials = cache
        return cache

    def _get_impersonate_credentials(self, user_email=None, scopes=None):
        """
        Retrieves and caches impersonated credentials using ADC and the injected service account.

        Args:
            user_email (str | None): The user to impersonate. Defaults to the injected user.
            scopes (list[str] | None): OAuth2 scopes. Defaults to GOOGLE_USER_SCOPES_LIST.

        Returns:
            google.auth.credentials.Credentials: Impersonated credentials.

        Raises:
            ValueError: If required values are missing or impersonation fails.
        """
        email = user_email or self._user_email
        scopes = scopes or GOOGLE_USER_SCOPES_LIST
        if not email:
            self.logger.error(
                f"Impersonation failed: environment variable {email} is not set."
            )
            raise ValueError(f"Please set environment variable: {email}.")

        if email in self._credentials:
            self.logger.info("Credentials are already cached.")
            return self._credentials[email]

        self._credentials[email], project_id = default()
        if not self._credentials[email]:
            self.logger.error(
                "Failed to obtain ADC credentials: no valid default credentials found."
            )
            raise ValueError("Google authentication service unavailable.")

        credentials_type = type(self._credentials[email])
        self.logger.info(
            f"Credentials retrieved successfully. Project ID: {project_id}. Credentials type: {credentials_type}"
        )

        try:
            self._credentials[email] = ImpersonatedCredentials(
                source_credentials=self._credentials[email],
                target_principal=self._service_account_email,
                target_scopes=scopes,
                subject=email,
            )

            self.logger.info(
                f"Successfully impersonated user: {email} using service account: {self._service_account_email}"
            )

        except Exception as e:
            original_error = str(e)
            self.logger.error(
                f"Impersonation failed with original error: {original_error}",
                exc_info=True,
            )
            self.logger.error(
                f"Impersonation troubleshooting details:\n"
                f"1. User email ('{email}') may be invalid or not in the Google Workspace domain.\n"
                f"2. Target service account ('{self._service_account_email}') may not have domain-wide delegation enabled.\n"
                f"3. Source credentials (from gcloud auth application-default login) may lack 'roles/iam.serviceAccountTokenCreator' role on the target service account.\n"
                f"   To fix, contact admin to grant your account this role.\n"
                f"4. IAM Credentials API may not be enabled (run: gcloud services enable iamcredentials.googleapis.com).\n"
                f"5. OAuth scopes ({GOOGLE_USER_SCOPES_LIST}) may not be authorized for domain-wide delegation.\n"
                f"For more details, refer to: https://cloud.google.com/iam/docs/service-account-impersonation"
            )
            raise ValueError(
                "Authentication failed. Please contact support for assistance."
            )

        return self._credentials[email]

    def _create_client(
        self, api_name: str, api_version: str, user_email=None, scopes=None
    ):
        """
        Creates a Google API client with retry logic via retry_utils.

        Args:
            api_name (str): The name of the API (e.g., "chat", "pubsub").
            api_version (str): The version of the API (e.g., "v1", "v1beta1").
            user_email (str | None): Optional user to impersonate.
            scopes (list[str] | None): OAuth2 scopes.

        Returns:
            _ThreadLocalResource: A client that builds one service per calling
                thread. It is used exactly like the underlying resource.

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

        def build_service():
            credentials = self.retry_utils.get_retry_on_transient(
                lambda: self._get_impersonate_credentials(
                    user_email=user_email, scopes=scopes
                )
            )
            if not credentials:
                raise ValueError(
                    "Credentials are not available for creating the client."
                )
            service = build(api_name, api_version, credentials=credentials)
            if not service:
                raise ValueError(f"Failed to create client for {api_name}.")
            self.logger.info(f"Created {api_name} client successfully.")
            return service

        return _ThreadLocalResource(build_service)

    def create_chat_client(self):
        """
        Creates a Google Chat API client.

        Returns:
            googleapiclient.discovery.Resource: The Google Chat API client, or None if an error occurs.
        """

        return self._create_client("chat", "v1")

    def create_people_client(self):
        """
        Creates a Google People API client.

        Returns:
            googleapiclient.discovery.Resource: The Google People API client, or None if an error occurs.
        """

        return self._create_client("people", "v1")

    def create_workspaceevents_client(self):
        """
        Creates a Google Workspace Events API client.

        This method initializes and returns a client for interacting with the Google Workspace Events API.
        If the client has not been created yet, it is instantiated using the `_create_client` method.

        Returns:
            googleapiclient.discovery.Resource: The Google Workspace Events API client instance.
        """

        return self._create_client("workspaceevents", "v1")

    def create_subscriber_client(self):
        """
        Creates a Google Cloud Pub/Sub subscriber client.

        Returns:
            pubsub_v1.SubscriberClient object if successful, else None.
        """

        return SubscriberClient()

    def create_publisher_client(self):
        """
        Creates a Google Cloud Pub/Sub Publisher client.

        Returns:
            google.cloud.pubsub_v1.PublisherClient: The Publisher client instance.
        """

        return PublisherClient()

    def create_calendar_client(self):
        """
        Creates a Google Calendar API client.

        Returns:
            googleapiclient.discovery.Resource: The Calendar API client instance.
        """

        return self._create_client("calendar", "v3")

    def create_reports_client(self):
        """
        Creates a Google Admin SDK Reports API client.

        Returns:
            googleapiclient.discovery.Resource: The Reports API client.
        """

        return self._create_client(
            "admin", "reports_v1", self._admin_email, GOOGLE_ADMIN_SCOPES_LIST
        )

    def create_meet_spaces_client(self):
        """
        Creates a Google Meet API v2 SpacesService async client.

        Returns:
            meet_v2.SpacesServiceAsyncClient
        """
        credentials = self.retry_utils.get_retry_on_transient(
            lambda: self._get_impersonate_credentials()
        )
        if not credentials:
            raise ValueError("Credentials are not available for creating the client.")
        client = meet_v2.SpacesServiceAsyncClient(
            credentials=credentials,
        )
        self.logger.info("Created Meet SpacesService client successfully.")
        return client

    def create_meet_conference_records_client(self):
        """
        Creates a Google Meet API v2 ConferenceRecordsService async client.

        Returns:
            meet_v2.ConferenceRecordsServiceAsyncClient
        """
        credentials = self.retry_utils.get_retry_on_transient(
            lambda: self._get_impersonate_credentials()
        )
        if not credentials:
            raise ValueError("Credentials are not available for creating the client.")
        client = meet_v2.ConferenceRecordsServiceAsyncClient(credentials=credentials)
        self.logger.info("Created Meet ConferenceRecordsService client successfully.")
        return client
