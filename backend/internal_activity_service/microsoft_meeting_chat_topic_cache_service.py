import os
from backend.common.constants import MICROSOFT_CHAT_TOPICS, MicrosoftChatType
from backend.common.environment_constants import (
    MICROSOFT_ADMIN_LDAP,
    MICROSOFT_USER_LDAP,
)


class MicrosoftMeetingChatTopicCacheService:
    """
    Service class responsible for managing and caching Microsoft Teams chat topic metadata.
    """

    def __init__(self, logger, redis_client, microsoft_service, retry_utils):
        """
        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            microsoft_service: The MicrosoftService instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.microsoft_service = microsoft_service
        self.retry_utils = retry_utils

    async def get_microsoft_chat_topics(self):
        """
        Retrieve cached Microsoft Teams meeting chat topics or fetch from Microsoft Graph if not cached.
        Returns:
            dict: Mapping of chat ID to chat topic.
        Raises:
            ValueError: If Redis client creation fails.
        """
        chat_topics = self.retry_utils.get_retry_on_transient(
            self.redis_client.hgetall, MICROSOFT_CHAT_TOPICS
        )
        if chat_topics:
            self.logger.info("Cache hit: Returning Microsoft chat topics from Redis.")
            return chat_topics

        topics_to_cache = await self.cache_chat_topics()
        return topics_to_cache

    async def cache_chat_topics(self):
        """
        Cache Microsoft Teams meeting chat topics in Redis.

        This function queries Microsoft Graph API to retrieve meeting chat topics for a specific user,
        whose LDAP is provided in the environment variable MICROSOFT_USER_LDAP. It then filters the chats
        to include only those created by the admin user (LDAP specified in MICROSOFT_ADMIN_LDAP), and stores
        the filtered topics in Redis.

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
        required_envs = []
        if not user_ldap:
            required_envs.append(MICROSOFT_USER_LDAP)
        if not admin_ldap:
            required_envs.append(MICROSOFT_ADMIN_LDAP)
        if required_envs:
            raise ValueError(
                f"Missing required environment variables: {', '.join(required_envs)}"
            )

        id_to_ldap_mapping = await self.microsoft_service.list_all_id_ldap_mapping()
        ldap_to_id_mapping = {val: key for key, val in id_to_ldap_mapping.items()}

        target_user_id = ldap_to_id_mapping.get(user_ldap)
        admin_id = ldap_to_id_mapping.get(admin_ldap)
        if not target_user_id or not admin_id:
            raise ValueError(
                f"User or admin ID not found in LDAP mapping: user={user_ldap}, admin={admin_ldap}"
            )

        chat_list = await self.microsoft_service.get_user_chats_by_user_id(
            target_user_id
        )
        if not chat_list:
            raise ValueError("No chat topics found for the user.")

        topics_to_cache = {}
        pipeline = self.redis_client.pipeline()
        for chat in chat_list:
            if (
                MicrosoftChatType.Meeting == chat.chat_type
                and admin_id == chat.online_meeting_info.organizer.id
            ):
                topics_to_cache[chat.id] = chat.topic
                pipeline.hset(MICROSOFT_CHAT_TOPICS, chat.id, chat.topic)

        self.retry_utils.get_retry_on_transient(pipeline.execute)

        self.logger.info(f"Cached {len(topics_to_cache)} chat topics to Redis.")

        return topics_to_cache
