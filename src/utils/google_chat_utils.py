from googleapiclient.errors import HttpError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from src.common.google_client import GoogleClientFactory
from src.common.logger import get_logger

logger = get_logger()


@retry(
    retry=retry_if_exception_type(HttpError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    reraise=True,
)
def _execute_request(request):
    return request.execute()


def get_chat_spaces(space_type, page_size):
    """Retrieves a dictionary of Google Chat spaces with their display names.

    Args:
        space_type (str): The type of spaces to filter (e.g., SPACE, ROOM).
        page_size (int): The number of spaces to retrieve per page.

    Returns:
        dict: A dictionary where keys are space IDs and values are display names, or None if an error occurs.

    Examples:
        {
            "BBBA9AJg-Ty": "CircleCat Mentorship Program,
            "BVDL3CTY-AD": "Engineering Team Chat"
        }
    Raises:
        ValueError: If no valid chat client provided.
        googleapiclient.errors.HttpError: If an error occurs during the API call.
    """
    client_chat = GoogleClientFactory().create_chat_client()
    if not client_chat:
        raise ValueError("No valid Chat client provided.")

    space_display_names = {}
    page_token = None

    while True:
        req = client_chat.spaces().list(
            pageSize=page_size,
            filter=f'space_type = "{space_type}"',
            pageToken=page_token,
        )
        try:
            response = _execute_request(req)
        except HttpError as e:
            logger.error(
                "External API error when fetching chat spaces (type=%s, page_token=%s): %s",
                space_type,
                page_token,
                e,
                exc_info=True,
            )
            raise RuntimeError("Unable to fetch chat spaces, external API error") from e

        spaces = response.get("spaces")
        if not spaces:
            raise ValueError(
                "Google Chat API response missing 'spaces' field in method get_chat_spaces"
            )

        for space in spaces:
            space_id = space.get("name").split("/")[1]
            display_name = space.get("displayName")
            space_display_names[space_id] = display_name

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    count = len(space_display_names)
    logger.info(f"Retrieved {count} {space_type} type Chat spaces.")
    return space_display_names
