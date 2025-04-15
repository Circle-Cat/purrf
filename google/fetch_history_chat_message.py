from google.authentication_utils import GoogleClientFactory
from google.chat_utils import get_chat_spaces, list_directory_all_people_ldap
from redis_dal.redis_utils import store_messages
from tools.log.logger import setup_logger
import logging
from google.constants import (
    NO_CLIENT_ERROR_MSG,
    CHAT_API_NAME,
    DEFAULT_PAGE_SIZE,
    FETCHING_MESSAGES_INFO_MSG,
    FETCHED_MESSAGES_INFO_MSG,
    DEFAULT_SPACE_TYPE,
    FETCHED_ALL_MESSAGES_INFO_MSG,
    SENDER_LDAP_NOT_FOUND_DEBUG_MSG,
    MESSAGE_TYPE_CREATE,
    STORED_MESSAGES_INFO_MSG,
)

setup_logger()


def fetch_messages_by_spaces_id(space_id):
    """
    Retrieves messages from a specific Google Chat space.

    This function fetches all messages from a given Google Chat space using the provided chat client.
    It handles pagination to retrieve all messages.

    Steps:
    1.  Validates the provided chat client.
    2.  Fetches messages from the specified space in batches using pagination.
    3.  Aggregates the messages into a single list.
    4.  Logs the number of messages retrieved.

    Args:
        space_id (str): The ID of the Google Chat space to fetch messages from.

    Returns:
        list: A list of message objects (dict) retrieved from the chat space.
        Returns None if the client is invalid.

    Raises:
        googleapiclient.errors.HttpError: If an error occurs during the API call.
        KeyError: If the expected data structure is not present in the API response.
        ValueError: If no valid chat client provided.
    """
    client_chat = GoogleClientFactory().create_chat_client()
    if not client_chat:
        raise ValueError(NO_CLIENT_ERROR_MSG.format(client_name=CHAT_API_NAME))

    logging.info(FETCHING_MESSAGES_INFO_MSG.format(space_id=space_id))
    result = []
    page_token = None
    while True:
        response = (
            client_chat.spaces()
            .messages()
            .list(
                parent=f"spaces/{space_id}",
                pageSize=DEFAULT_PAGE_SIZE,
                pageToken=page_token,
            )
            .execute()
        )
        messages = response.get("messages", [])
        result.extend(messages)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    logging.info(FETCHED_MESSAGES_INFO_MSG.format(count=len(result), space_id=space_id))
    return result


def fetch_history_messages():
    """
    Processes chat spaces by fetching messages and storing them in Redis.

    This function performs the following steps:
    1.  Retrieves Google Chat and People API clients using the GoogleClientFactory.
    2.  Fetches a list of chat space IDs.
    3.  Iterates through each space ID, retrieves messages, and aggregates them.
    4.  Loads a dictionary mapping sender IDs to their LDAP identifiers.
    5.  Processes each message:
        a.  Extracts the sender ID and retrieves the corresponding LDAP.
        b.  Skips messages if the sender's LDAP is not found, indicating an external account.
        c.  Stores the message in Redis using the 'store_messages' function.
    6.  Logs the number of messages fetched and successfully stored.

    Returns:
        None.
    """
    messages = []

    space_id_list = get_chat_spaces(DEFAULT_SPACE_TYPE, DEFAULT_PAGE_SIZE)

    for space_id in space_id_list.keys():
        result = fetch_messages_by_spaces_id(space_id)
        messages.extend(result)
        logging.debug(
            FETCHED_MESSAGES_INFO_MSG.format(count=len(result), space_id=space_id)
        )

    logging.info(FETCHED_ALL_MESSAGES_INFO_MSG.format(count=len(messages)))

    people_dict = list_directory_all_people_ldap()

    stored_count = 0
    for message in messages:
        _, sender_id = message.get("sender", {}).get("name").split("/")
        sender_ldap = people_dict.get(sender_id, "")
        if not sender_ldap:
            logging.debug(
                SENDER_LDAP_NOT_FOUND_DEBUG_MSG.format(
                    sender_id=sender_id, message=message
                )
            )
            continue

        store_messages(sender_ldap, message, MESSAGE_TYPE_CREATE)
        stored_count += 1

    logging.info(
        STORED_MESSAGES_INFO_MSG.format(
            stored_count=stored_count, total_count=len(messages)
        )
    )
    return STORED_MESSAGES_INFO_MSG.format(
        stored_count=stored_count, total_count=len(messages)
    )
