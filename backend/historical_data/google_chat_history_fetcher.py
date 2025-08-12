from backend.utils.google_chat_utils import get_chat_spaces
from backend.utils.google_chat_message_store import store_messages
from backend.common.google_client import GoogleClientFactory
from backend.common.logger import get_logger
from googleapiclient.errors import HttpError
from backend.common.constants import GoogleChatEventType
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = get_logger()


@retry(
    retry=retry_if_exception_type(HttpError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    reraise=True,
)
def _execute_request(request):
    return request.execute()


def list_directory_all_people_ldap():
    """
    Retrieves a dictionary of sender IDs to LDAP identifiers from the Google People API.

    This function fetches all directory people from the Google People API, extracts their sender IDs and LDAP
    identifiers, and returns them as a dictionary.

    Steps:
    1.  Validates the provided People API client.
    2.  Fetches directory people in batches using pagination.
    3.  Extracts the sender ID and LDAP identifier from each person's email address.
    4.  Stores the sender ID and LDAP identifier in a dictionary.
    5.  Logs the number of people retrieved from the directory.

    Returns:
        dict: A dictionary mapping sender IDs (str) to LDAP identifiers (str).

    Raises:
        ValueError: If no valid people client provided.
        googleapiclient.errors.HttpError: If an error occurs during the API call.
        KeyError: If the expected data structure is not present in the API response.
        IndexError: If the email address list is empty.
    """
    client_people = GoogleClientFactory().create_people_client()
    if not client_people:
        raise ValueError(
            "Failed to fetch historical chat messages: Google People client is unavailable."
        )

    directory_people = []
    formatted_people = {}
    page_token = None
    while True:
        req = client_people.people().listDirectoryPeople(
            readMask="emailAddresses",
            pageSize=100,
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageToken=page_token,
        )
        try:
            response = _execute_request(req)
        except HttpError as e:
            logger.error(
                "Error fetching directory people (page_token=%s): %s",
                page_token,
                e,
                exc_info=True,
            )
            raise RuntimeError("Unable to fetch directory people") from e

        people = response.get("people")
        if people is None:
            raise ValueError(
                "list_directory_all_people_ldap is missing 'people' field "
            )

        directory_people.extend(people)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    for person in directory_people:
        emailAddresses_data = person.get("emailAddresses")[0]
        id = emailAddresses_data.get("metadata", {}).get("source", {}).get("id", {})
        ldap = emailAddresses_data.get("value", "").split("@")[0]
        formatted_people[id] = ldap

    if not formatted_people:
        raise ValueError("No directory people were found in the domain.")

    logger.info(
        "Successfully retrieved %d directory people from Google Workspace.",
        len(formatted_people),
    )
    return formatted_people


def fetch_messages_by_spaces_id(space_id):
    """
    Retrieves messages from a specific Google Chat space.
    This function fetches all messages from a given Google Chat space using the provided chat client.
    It handles pagination to retrieve all messages.

    Steps:
    1.  Validates the created chat client.
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
        raise ValueError(
            "Failed to fetch historical chat messages: Google Chat client is unavailable."
        )
    logger.debug("Fetching messages from Google Chat space: %s", space_id)
    result = []
    page_token = None
    while True:
        req = (
            client_chat.spaces()
            .messages()
            .list(
                parent=f"spaces/{space_id}",
                pageSize=100,
                pageToken=page_token,
            )
        )
        try:
            response = _execute_request(req)
        except HttpError as e:
            logger.error(
                "Error fetching chat messages (page_token=%s): %s",
                page_token,
                e,
                exc_info=True,
            )
            raise RuntimeError("Unable to fetch Google Chat messages") from e
        messages = response.get("messages", [])
        result.extend(messages)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    logger.info(
        "Fetched %d messages from Google Chat in space: %s", len(result), space_id
    )
    return result


def fetch_history_messages():
    """
    Processes chat spaces by fetching messages and storing them in Redis.

    Steps:
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
    space_id_list = get_chat_spaces("SPACE", 100)
    for space_id in space_id_list.keys():
        result = fetch_messages_by_spaces_id(space_id)
        messages.extend(result)
        logger.debug("Fetched %d messages from space %s", len(result), space_id)
    logger.info("Fetched total of %d messages from all spaces", len(messages))
    people_dict = list_directory_all_people_ldap()
    saved_count = 0
    for message in messages:
        _, sender_id = message.get("sender", {}).get("name").split("/")
        sender_ldap = people_dict.get(sender_id, "")
        if not sender_ldap:
            logger.debug(
                "No LDAP found for sender_id=%s in message: %s", sender_id, message
            )
            continue
        store_messages(sender_ldap, message, GoogleChatEventType.CREATED.value)
        saved_count += 1
    logger.info(
        "Stored %d out of %d messages with valid sender LDAP",
        saved_count,
        len(messages),
    )
    return {"saved_messages_count": saved_count, "total_messges_count": len(messages)}
