from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph.generated.chats.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)
from src.common.microsoft_client import MicrosoftClientFactory
from src.common.logger import get_logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.historical_data.microsoft_ldap_fetcher import get_all_microsoft_members
from src.utils.microsoft_chat_message_store import sync_history_chat_messages_to_redis
from src.common.constants import (
    MICROSOFT_TEAMS_MESSAGES_SORTER,
    MICROSOFT_TEAMS_MESSAGES_MAX_RESULT,
)

logger = get_logger()


async def list_all_id_ldap_mapping() -> dict:
    """
    Retrieves all Microsoft user IDs and maps them to their LDAP identifiers (email local parts).

    Returns:
        dict: A mapping from Microsoft user ID to LDAP username.
    """
    result = await get_all_microsoft_members()

    users_info = {}
    for user in result:
        if user.mail:
            email_local_part, _ = user.mail.split("@")
            users_info[user.id] = email_local_part

    return users_info


async def get_microsoft_chat_messages_by_chat_id(chat_id: str):
    """
    Asynchronously fetches all messages in a Microsoft chat by chat ID, yielding pages of messages.

    Args:
        chat_id (str): The unique identifier of the Microsoft chat.

    Yields:
        list: A list of message objects from the current page.

    Raises:
        ValueError: If the Microsoft Graph client could not be created.
        Exception: If message fetching fails after retries.
    """
    graph_client = MicrosoftClientFactory().create_graph_service_client()
    if not graph_client:
        raise ValueError("Microsoft Graph client not created.")
    query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        orderby=MICROSOFT_TEAMS_MESSAGES_SORTER, top=MICROSOFT_TEAMS_MESSAGES_MAX_RESULT
    )

    initial_request_configuration = RequestConfiguration(
        query_parameters=query_params,
    )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _fetch_single_page(url: str = None):
        """
        Fetches a single page of messages from Microsoft Graph API with retry support.

        Args:
            url (str, optional): The nextLink URL for pagination. If not provided, fetches the first page.

        Returns:
            MessagesCollectionResponse: The API response containing messages and potentially a nextLink.
        """
        if url:
            logger.debug(f"Fetching next page from URL: {url}")
            return (
                await graph_client.chats.by_chat_id(chat_id)
                .messages.with_url(url)
                .get()
            )
        else:
            logger.debug("Fetching initial page.")
            return await graph_client.chats.by_chat_id(chat_id).messages.get(
                request_configuration=initial_request_configuration
            )

    current_page = await _fetch_single_page()

    while current_page:
        messages = current_page.value or []
        if messages:
            yield messages

        next_link = current_page.odata_next_link

        if not next_link:
            break

        current_page = await _fetch_single_page(next_link)


async def sync_microsoft_chat_messages_by_chat_id(chat_id: str) -> dict:
    """
    Asynchronously syncs Microsoft chat messages for a specific chat ID by retrieving the messages in pages,
    processing each page to filter and store the undeleted messages in Redis, and tracking the total processed and
    skipped messages.

    Args:
        chat_id (str): The unique identifier for the Microsoft chat whose messages need to be synced.

    Returns:
        dict: A dictionary containing two keys:
            - "total_processed" (int): The total number of messages successfully processed and stored in Redis.
            - "total_skipped" (int): The total number of messages skipped due to being deleted or invalid.
    """
    overall_total_processed = 0
    overall_total_skipped = 0
    message_buffer = []
    buffer_count = 10
    count = 0
    all_ldaps = await list_all_id_ldap_mapping()
    async for page_messages in get_microsoft_chat_messages_by_chat_id(chat_id):
        if not page_messages:
            logger.debug(f"No messages in current page for chat ID: {chat_id}")
            continue

        message_buffer.extend(page_messages)
        count += 1

        if count >= buffer_count:
            messages_count = len(message_buffer)
            logger.info(
                f"Buffer reached {messages_count} messages. Syncing batch to Redis for chat ID: {chat_id}"
            )
            processed_in_batch, skipped_in_batch = sync_history_chat_messages_to_redis(
                message_buffer, all_ldaps
            )
            overall_total_processed += processed_in_batch
            overall_total_skipped += skipped_in_batch
            message_buffer = []
            count = 0

    if message_buffer:
        logger.info(
            f"Processing remaining {len(message_buffer)} messages in buffer for chat ID: {chat_id}"
        )
        processed_in_batch, skipped_in_batch = sync_history_chat_messages_to_redis(
            message_buffer, all_ldaps
        )
        overall_total_processed += processed_in_batch
        overall_total_skipped += skipped_in_batch

    logger.info(
        f"Completed syncing for chat ID: {chat_id}. Total processed: {overall_total_processed}, total skipped: {overall_total_skipped}."
    )
    return {
        "total_processed": overall_total_processed,
        "total_skipped": overall_total_skipped,
    }
