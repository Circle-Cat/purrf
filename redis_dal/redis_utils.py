from redis_dal.redis_client_factory import RedisClientFactory
from datetime import datetime
from tools.log.logger import setup_logger
import logging
from redis_dal.constants import REDIS_KEY_FORMAT, REDIS_MESSAGE_STORED_DEBUG_MSG

setup_logger()


def store_messages(sender_ldap, message, message_type):
    """
    Stores a message in Redis with a sorted set using sender LDAP as part of the key.

    This function retrieves a Redis client, extracts relevant information from the message,
    and stores it in a sorted set in Redis. The sorted set's key is constructed using the
    space name and sender LDAP, and the score is the message's creation timestamp.

    Args:
        sender_ldap (str): The LDAP identifier of the message sender.
        message (dict): The message object (dictionary) to be stored.
        message_type (str): The type of the message (e.g., "create").

    Raises:
        ValueError: If the 'createTime' in the message is not in a valid ISO format.
        redis.exceptions.RedisError: If an error occurs during Redis operations.

    Example:
        store_messages("name", {"createTime": "2023-10-27T10:00:00Z", "space": {"name": "MySpace"}, ...}, "create")
    """

    client_redis = RedisClientFactory().create_redis_client()
    create_time = message.get("createTime")
    space_id = message.get("space", {}).get("name").split("/")[1]
    score = datetime.fromisoformat(create_time).timestamp()
    redis_key = REDIS_KEY_FORMAT.format(space_id=space_id, sender_ldap=sender_ldap)
    redis_member = {"message": message, "type": message_type}
    client_redis.zadd(redis_key, {str(redis_member): score})
    logging.debug(
        REDIS_MESSAGE_STORED_DEBUG_MSG.format(redis_key=redis_key, score=score)
    )
