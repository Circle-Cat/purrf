from src.common.microsoft_client import MicrosoftClientFactory
from src.common.logger import get_logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph.generated.users.users_request_builder import UsersRequestBuilder
from src.common.redis_client import RedisClientFactory
from src.common.constants import (
    MicrosoftAccountStatus,
    MICROSOFT_LDAP_KEY,
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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def sync_microsoft_members_to_redis():
    """
    Fetches Microsoft 365 user information and caches it in Redis for fast lookup.

    This function retrieves a list of Microsoft 365 members whose email ends with 'circlecat.org',
    processes each user's data by extracting their LDAP (local part before '@') and display name,
    and determines their account status (active or terminated) based on the `accountEnabled` flag.

    The method then stores one hash mapping in Redis for each user:
    - Key: `ldap:{account_status}` — maps LDAP to display name.

    This method employs an incremental update strategy.
    The update logic performs the following:
    1. **Compares current Redis data** with the latest Microsoft Graph data.
    2. **Adds/Updates active users**: If an active user is new to Redis or their display name has changed,
       their entry is added or updated in the `ldap:active` Hash.
    3. **Handles status changes to active**: If a user is now active but was previously terminated,
       their entry is removed from the `ldap:terminated` to `ldap:active` Hash.
    4. **Handles status changes to terminated**: If a user is now terminated but was previously active,
       their entry is removed from the `ldap:active` to `ldap:terminated` Hash.

    Raises:
        ValueError: If Redis client creation fails.
        RuntimeError: If user retrieval from Microsoft Graph fails.

    Returns:
        dict: A response counts of active and terminated users.
            Example:
                {
                    "activated": 56,
                    "terminated": 10,
                }
    """
    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")

    members_info = await get_all_microsoft_members()

    if not members_info:
        logger.error("No Microsoft 365 users found matching the domain filter.")
        raise RuntimeError("No Microsoft 365 users were fetched from Graph API.")

    active_redis_key = MICROSOFT_LDAP_KEY.format(
        account_status=MicrosoftAccountStatus.ACTIVE.value
    )
    terminated_redis_key = MICROSOFT_LDAP_KEY.format(
        account_status=MicrosoftAccountStatus.TERMINATED.value
    )

    current_active_ldaps_and_names = redis_client.hgetall(active_redis_key)
    current_terminated_ldaps = redis_client.hkeys(terminated_redis_key)

    new_active_members = {}
    new_terminated_members = {}

    added_active = set()
    moved_to_active = set()
    moved_to_terminated = set()

    for member in members_info:
        ldap = member.mail.split("@")[0]
        display_name = member.display_name
        status = (
            MicrosoftAccountStatus.ACTIVE.value
            if member.account_enabled
            else MicrosoftAccountStatus.TERMINATED.value
        )

        if status == MicrosoftAccountStatus.ACTIVE.value:
            new_active_members[ldap] = display_name
        else:
            new_terminated_members[ldap] = display_name

    pipe = redis_client.pipeline()

    for ldap, display_name in new_active_members.items():
        if (
            ldap not in current_active_ldaps_and_names
            or current_active_ldaps_and_names.get(ldap) != display_name
        ):
            pipe.hset(active_redis_key, ldap, display_name)
            added_active.add(display_name)
        if ldap in current_terminated_ldaps:
            pipe.hdel(terminated_redis_key, ldap)
            moved_to_active.add(display_name)

    for ldap, display_name in new_terminated_members.items():
        if ldap not in current_terminated_ldaps:
            pipe.hset(terminated_redis_key, ldap, display_name)
            pipe.hdel(active_redis_key, ldap)
            moved_to_terminated.add(display_name)

    try:
        pipe.execute()
        logger.info(
            f"Successfully synchronized Redis data. "
            f"Active users: {len(new_active_members)}, Terminated users: {len(new_terminated_members)}. "
        )
    except Exception as e:
        logger.error(f"Redis pipeline execution failed: {e}")
        raise RuntimeError("Failed to update LDAP data in Redis.") from e

    if added_active:
        logger.info(f"Added active users: {', '.join(added_active)}")
    if moved_to_active:
        logger.info(f"Moved to active (from terminated): {', '.join(moved_to_active)}")
    if moved_to_terminated:
        logger.info(
            f"Moved to terminated (from active): {', '.join(moved_to_terminated)}"
        )

    return {
        MicrosoftAccountStatus.ACTIVE.value: len(new_active_members),
        MicrosoftAccountStatus.TERMINATED.value: len(new_terminated_members),
    }
