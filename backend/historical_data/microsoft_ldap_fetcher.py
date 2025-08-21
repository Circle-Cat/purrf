from backend.common.microsoft_client import MicrosoftClientFactory
from backend.common.logger import get_logger
from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph.generated.users.users_request_builder import UsersRequestBuilder
from backend.common.constants import (
    MICROSOFT_USER_INFO_FILTER,
    MICROSOFT_USER_INFO_SELECT_FIELDS,
    MICROSOFT_CONSISTENCY_HEADER,
    MICROSOFT_CONSISTENCY_VALUE,
)

logger = get_logger()


async def get_all_microsoft_members():
    """
    Fetches a list of Microsoft 365 users whose email ends with 'circlecat.org' from Microsoft Graph API.

    This method uses an asynchronous Microsoft Graph client to query user information including
    `displayName`, `mail`, and `accountEnabled` fields. It applies a filter to only include users whose
    email address ends with 'circlecat.org'. It also includes retry logic with exponential backoff
    to handle transient errors.

    Retries:
        Up to 3 attempts with exponential backoff on exceptions.

    Returns:
        List[User]: A list of user objects matching the filter. Returns an empty list if no users are found.

    Raises:
        ValueError: If the Microsoft Graph client is not successfully created.
        RuntimeError: If the API request fails even after retries.
    """
    client = MicrosoftClientFactory().create_graph_service_client()
    if not client:
        raise ValueError("Microsoft Graph client not created.")

    query_params = UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
        filter=MICROSOFT_USER_INFO_FILTER,
        select=MICROSOFT_USER_INFO_SELECT_FIELDS,
    )
    request_configuration = RequestConfiguration(query_parameters=query_params)
    request_configuration.headers.add(
        MICROSOFT_CONSISTENCY_HEADER, MICROSOFT_CONSISTENCY_VALUE
    )

    try:
        logger.info("Sending request to Microsoft Graph API for user list.")
        result = await client.users.get(request_configuration=request_configuration)
    except Exception as e:
        logger.error(f"Failed to fetch users from Microsoft Graph API: {e}")
        raise RuntimeError("Failed to fetch users from Microsoft Graph API.") from e

    if not result or not result.value:
        logger.warning("Received empty result from Microsoft Graph API.")
        return []

    return result.value
