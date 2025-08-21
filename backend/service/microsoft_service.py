import logging
from http import HTTPStatus

from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph.generated.users.users_request_builder import UsersRequestBuilder
from msgraph.generated.chats.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)
from msgraph.generated.models.subscription import Subscription
from msgraph.generated.models.chat_message_collection_response import (
    ChatMessageCollectionResponse,
)
from msgraph.generated.models.chat_message import ChatMessage
from msgraph import GraphServiceClient
from backend.common.constants import (
    MICROSOFT_USER_INFO_FILTER,
    MICROSOFT_USER_INFO_SELECT_FIELDS,
    MICROSOFT_CONSISTENCY_HEADER,
    MICROSOFT_CONSISTENCY_VALUE,
    MICROSOFT_TEAMS_MESSAGES_SORTER,
    MICROSOFT_TEAMS_MESSAGES_MAX_RESULT,
)
from backend.utils.retry_utils import RetryUtils


class MicrosoftService:
    """
    A service class that encapsulates interactions with the Microsoft Graph API.

    This class provides methods to interact with Microsoft 365 user data via the Graph API,
    including support for retries on transient failures. It is designed to isolate SDK usage
    and allow for better testability and decoupling from business logic.

    Args:
        logger (logging.Logger): Logger instance for logging info and errors.
        graph_service_client (GraphServiceClient): Microsoft Graph client instance.
        retry_utils (RetryUtils): Utility class for handling retries.


    Raises:
        ValueError: If required parameters are not provided.
    """

    def __init__(
        self,
        logger: logging.Logger,
        graph_service_client: GraphServiceClient,
        retry_utils: RetryUtils,
    ):
        """Initialize the MicrosoftService."""
        self.logger = logger
        self.graph_service_client = graph_service_client
        self.retry_utils = retry_utils

    async def get_all_microsoft_members(self) -> list:
        """
        Fetches a list of Microsoft 365 users whose email ends with 'circlecat.org' from Microsoft Graph API.

        This method uses an asynchronous Microsoft Graph client to query user information including
        `displayName`, `mail`, and `accountEnabled` fields. It applies a filter to only include users whose
        email address ends with 'circlecat.org'. It also includes retry logic with exponential backoff
        to handle transient errors.

        Returns:
            List[User]: A list of user objects matching the filter. Returns an empty list if no users are found.
        """
        query_params = UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
            filter=MICROSOFT_USER_INFO_FILTER,
            select=MICROSOFT_USER_INFO_SELECT_FIELDS,
        )
        request_configuration = RequestConfiguration(query_parameters=query_params)
        request_configuration.headers.add(
            MICROSOFT_CONSISTENCY_HEADER, MICROSOFT_CONSISTENCY_VALUE
        )

        self.logger.info("Sending request to Microsoft Graph API for user list.")

        result = await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.users.get,
            request_configuration=request_configuration,
        )

        if not result or not result.value:
            self.logger.warning("Received empty result from Microsoft Graph API.")
            return []

        return result.value

    async def fetch_initial_chat_messages_page(
        self, chat_id: str
    ) -> ChatMessageCollectionResponse:
        """
        Fetches the first page of chat messages for a given Microsoft Teams chat ID.

        Args:
            chat_id (str): The unique ID of the Microsoft Teams chat.

        Returns:
            ChatMessageCollectionResponse: A response object with the first page of chat messages.

        ValueError: If `chat_id` is not provided.
        """
        if not chat_id:
            raise ValueError("Chat ID is required.")

        self.logger.debug("Fetching initial page.")

        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            orderby=MICROSOFT_TEAMS_MESSAGES_SORTER,
            top=MICROSOFT_TEAMS_MESSAGES_MAX_RESULT,
        )
        initial_request_configuration = RequestConfiguration(
            query_parameters=query_params,
        )
        result = await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.chats.by_chat_id(chat_id).messages.get,
            request_configuration=initial_request_configuration,
        )

        return result

    async def fetch_chat_messages_by_url(
        self, chat_id: str, url: str
    ) -> ChatMessageCollectionResponse:
        """
        Fetches the next page of chat messages using a pagination URL.

        Args:
            chat_id (str): The Microsoft Teams chat ID.
            url (str): The pagination URL.

        Returns:
            ChatMessageCollectionResponse: A response object with the next page of chat messages.

        ValueError:
            - If `chat_id` is not provided.
            - If `url` is not provided.
        """
        if not chat_id:
            raise ValueError("Chat ID is required.")
        if not url:
            raise ValueError("Pagination URL is required.")

        self.logger.debug(f"Fetching next page from URL: {url}")
        return await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.chats.by_chat_id(chat_id)
            .messages.with_url(url)
            .get
        )

    async def get_ldap_by_id(self, user_id: str) -> str | None:
        """
        Retrieves a user's LDAP identifier using their Microsoft Graph API user ID.

        Fetches user details from Microsoft Graph API and extracts the LDAP
        identifier from the user's email address.

        Args:
            user_id (str): The Microsoft Graph API user ID of the user.

        Returns:
            str or None: The user's LDAP identifier if valid; None if the user is not found
                         or if the email is missing or improperly formatted.

        Raises:
            ValueError: If the user ID is not provided.
        """
        if not user_id:
            raise ValueError("User ID is required.")
        try:
            result = await self.retry_utils.get_retry_on_transient(
                self.graph_service_client.users.by_user_id(user_id).get
            )
        except Exception as e:
            if (
                hasattr(e, "response_status_code")
                and e.response_status_code == HTTPStatus.NOT_FOUND
            ):
                self.logger.info(f"User ID '{user_id}' not found in Microsoft Graph.")
                return None
            raise e
        mail = result.mail
        if not mail or "@" not in mail:
            self.logger.warning(
                f"Invalid or missing email for user ID '{user_id}': {mail}"
            )
            return None
        ldap, _ = mail.split("@")
        return ldap

    async def get_message_by_id(self, chat_id: str, message_id: str) -> ChatMessage:
        """
        Retrieves a specific Microsoft Teams chat message by its message ID and chat ID.

        This method uses the Microsoft Graph API to fetch a single message from a specified
        Teams chat. Retry logic with exponential backoff is applied to handle transient
        failures such as network issues or service instability.

        Args:
            chat_id (str): The unique identifier of the Teams chat where the message is located.
            message_id (str): The unique identifier of the specific message to retrieve.

        Returns:
            ChatMessage: The retrieved Microsoft Teams chat message object.

        Raises:
            ValueError:
                - If `chat_id` is not provided.
                - If `message_id` is not provided.
        """
        if not chat_id:
            raise ValueError("Chat ID is required.")

        if not message_id:
            raise ValueError("Message ID is required.")

        message = await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.chats.by_chat_id(chat_id)
            .messages.by_chat_message_id(message_id)
            .get
        )

        return message

    async def list_all_id_ldap_mapping(self) -> dict:
        """
        Retrieves all Microsoft user IDs and maps them to their LDAP identifiers (email local parts).

        Returns:
            dict: A mapping from Microsoft user ID to LDAP username.
        """
        result = await self.get_all_microsoft_members()

        users_info = {}
        for user in result:
            if user.mail and "@" in user.mail:
                email_local_part, _ = user.mail.split("@")
                users_info[user.id] = email_local_part

        return users_info

    async def get_user_chats_by_user_id(self, user_id: str) -> list:
        """
        Retrieves all chats for a given user ID.

        Raises:
            ValueError: If `user_id` is not provided.
        """
        if not user_id:
            raise ValueError("User ID is required.")

        result = await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.users.by_user_id(user_id).chats.get
        )

        return result.value

    async def list_all_subscriptions(self) -> list:
        """
        Retrieve all active Microsoft Graph subscriptions.

        Retries up to 3 times with exponential backoff if an exception other than
        `ValueError` is raised.

        Returns:
            List[Subscription]: A list of Microsoft Graph `Subscription` objects.
        """
        subscriptions = await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.subscriptions.get
        )
        return subscriptions.value

    async def delete_subscription(self, subscription_id: str):
        """
        Delete a Microsoft Graph subscription by its ID.

        Retries up to 3 times with exponential backoff if an exception other than
        `ValueError` is raised.

        Args:
            subscription_id (str): The unique identifier of the subscription to delete.

        Raises:
            Any exceptions raised by the Microsoft Graph SDK except `ValueError`.
        """
        await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.subscriptions.by_subscription_id(
                subscription_id
            ).delete
        )

    async def create_subscription(
        self,
        change_type: str,
        notification_url: str,
        lifecycle_notification_url: str,
        resource: str,
        expiration_date_time: str,
        client_state: str,
    ) -> Subscription:
        """
        Create a new Microsoft Graph subscription for Teams chat messages.

        Args:
            change_type_str (str): Comma-separated change types (e.g., "created,updated").
            notification_url (str): Webhook endpoint to receive change notifications.
            lifecycle_notification_url (str): URL to receive lifecycle events (e.g., reauthorization).
            resource (str): Resource path to subscribe to (e.g., a specific chat).
            expiration_date_time (str): ISO-formatted expiration datetime string.
            client_state (str): A random client state string to validate notifications.

        Returns:
            Subscription: The created subscription object returned by Microsoft Graph.
        """
        request_body = Subscription(
            change_type=change_type,
            notification_url=notification_url,
            lifecycle_notification_url=lifecycle_notification_url,
            resource=resource,
            expiration_date_time=expiration_date_time,
            client_state=client_state,
        )
        result = await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.subscriptions.post, request_body
        )
        return result

    async def list_all_groups(self) -> list:
        """
        Retrieves all Microsoft 365 groups using Microsoft Graph API.

        Returns:
            List[Group]: A list of Microsoft Graph Group objects.
        """
        result = await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.groups.get
        )
        return result.value

    async def get_group_members(self, group_id: str) -> list:
        """
        Retrieves members of a specified Microsoft 365 group.

        Args:
            group_id (str): The unique ID of the Microsoft 365 group.

        Returns:
            List[DirectoryObject]: A list of member objects in the group.

        Raises:
            ValueError: If the provided group_id is empty or None.
        """
        if not group_id:
            raise ValueError("Group ID is required.")

        result = await self.retry_utils.get_retry_on_transient(
            self.graph_service_client.groups.by_group_id(group_id).members.get
        )

        return result.value
