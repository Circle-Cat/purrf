import os

from msgraph.generated.models.chat_type import ChatType

from backend.common.logger import get_logger
from backend.common.constants import MICROSOFT_CHAT_TOPICS
from backend.common.environment_constants import (
    MICROSOFT_ADMIN_LDAP,
    MICROSOFT_USER_LDAP,
)
from backend.common.redis_client import RedisClientFactory
from backend.common.microsoft_client import MicrosoftClientFactory
from backend.historical_data.microsoft_chat_history_fetcher import (
    list_all_id_ldap_mapping,
)

logger = get_logger()


async def get_microsoft_chat_topics():
    """
    Retrieve cached Microsoft Teams meeting chat topics or fetch from Microsoft Graph if not cached.

    Returns:
        dict: Mapping of chat ID to chat topic.

    Raises:
        ValueError: If Redis client creation fails.
    """
    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")

    chat_topics = redis_client.hgetall(MICROSOFT_CHAT_TOPICS)
    if chat_topics:
        logger.info("Cache hit: Returning Microsoft chat topics from Redis.")
        return chat_topics

    topics_to_cache = await cache_chat_topics(redis_client)
    return topics_to_cache


async def cache_chat_topics(redis_client):
    """
    Cache Microsoft Teams meeting chat topics in Redis.

    This function queries Microsoft Graph API to retrieve meeting chat topics for a specific user,
    whose LDAP is provided in the environment variable MICROSOFT_USER_LDAP. It then filters the chats
    to include only those created by the admin user (LDAP specified in MICROSOFT_ADMIN_LDAP), and stores
    the filtered topics in Redis.

    Args:
        redis_client: The Redis client used to cache the chat topics.

    Returns:
        dict: A dictionary of chat IDs and their corresponding topics,
              to be stored in Redis as the cache.

    Raises:
        ValueError: If the required environment variables (MICROSOFT_USER_LDAP or MICROSOFT_ADMIN_LDAP)
                    are not found, if no user/admin ID is found in the LDAP mapping, or if no chat topics
                    are found for the user.
    """
    user_ldap = os.environ.get(MICROSOFT_USER_LDAP)
    admin_ldap = os.environ.get(MICROSOFT_ADMIN_LDAP)
    if not user_ldap or not admin_ldap:
        raise ValueError(
            f"Missing required environment variables: "
            f"{MICROSOFT_USER_LDAP} or {MICROSOFT_ADMIN_LDAP}"
        )

    all_ldaps = await list_all_id_ldap_mapping()
    target_user_id = None
    admin_id = None
    for key, val in all_ldaps.items():
        if val == user_ldap:
            target_user_id = key
        elif val == admin_ldap:
            admin_id = key
        if target_user_id and admin_id:
            break
    if not target_user_id or not admin_id:
        raise ValueError(
            f"User or admin ID not found in LDAP mapping: user={user_ldap}, admin={admin_ldap}"
        )

    graph_client = MicrosoftClientFactory().create_graph_service_client()
    if not graph_client:
        raise ValueError("Microsoft Graph client not created.")

    response = await graph_client.users.by_user_id(target_user_id).chats.get()
    chat_list = response.value
    if not chat_list:
        raise ValueError("No chat topics found for the user.")

    topics_to_cache = {}
    pipeline = redis_client.pipeline()
    for chat in chat_list:
        # Filter: Only meeting chats for this specific user, created by the admin
        if (
            chat.chat_type == ChatType.Meeting
            and chat.online_meeting_info.organizer.id == admin_id
        ):
            topics_to_cache[chat.id] = chat.topic
            pipeline.hset(MICROSOFT_CHAT_TOPICS, chat.id, chat.topic)

    # To enable periodic cache refresh, set an expiration time for the key.
    # After the set TTL, the key-value will be automatically deleted and refreshed.
    # Example:
    # pipeline.expire(key, time)

    pipeline.execute()
    logger.info(f"Cached {len(topics_to_cache)} chat topics to Redis.")

    return topics_to_cache
