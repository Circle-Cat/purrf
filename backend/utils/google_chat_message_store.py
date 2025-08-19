from backend.common.redis_client import RedisClientFactory
from datetime import datetime
import json
from typing import Optional
from dataclasses import dataclass
from backend.common.logger import get_logger
from backend.common.constants import (
    CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY,
    DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY,
    GoogleChatEventType,
)

logger = get_logger()


@dataclass
class StoredMessage:
    sender: str
    threadId: str
    text: list
    is_deleted: bool
    attachment: Optional[list] = None


def _handle_create_message(sender_ldap: str, message: dict):
    """
    Handle a CREATED Google Chat message by storing the new message in Redis
    and adding its ID to a sorted set index for efficient retrieval.

    This function performs the following steps:
    1. Parses the message name and extracts relevant IDs (space and message IDs).
    2. Converts the message's creation time to a timestamp to use as the sorted set score.
    3. Constructs a Redis sorted set key scoped by space ID and sender LDAP.
    4. Extracts the thread ID from the message thread metadata.
    5. Wraps the message details in a `StoredMessage` dataclass instance.
    6. Uses a Redis pipeline to atomically:
       - Add the message ID to the sorted set with the creation timestamp as score.
       - Store the serialized message under its Redis key.
    7. Handles exceptions during Redis operations and logs errors.

    Args:
        sender_ldap (str): LDAP identifier of the sender of the message.
        message (dict): A dictionary containing message data.

    Raises:
        ValueError: If Redis client creation fails.
        Exception: On failure during Redis pipeline execution.
    """
    message_name = message.get("name")
    client_redis = RedisClientFactory().create_redis_client()
    if not client_redis:
        raise ValueError(
            "Failed to create Redis client when saving new Google Chat message."
        )
    _, space_id, _, message_id = message_name.split("/")
    create_time = message.get("createTime")
    index_score = datetime.fromisoformat(create_time).timestamp()
    index_redis_key = CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
        space_id=space_id, sender_ldap=sender_ldap
    )

    thread_name = message.get("thread", {}).get("name", "")
    _, _, _, thread_id = thread_name.split("/")
    logger.debug(f"Parsed thread name: thread_id={thread_id}")
    text_content = {"value": message.get("text"), "createTime": create_time}
    saved_message = StoredMessage(
        sender=sender_ldap,
        threadId=thread_id,
        text=[text_content],
        is_deleted=False,
        attachment=message.get("attachment"),
    )

    try:
        pipeline = client_redis.pipeline()
        pipeline.zadd(index_redis_key, {message_id: index_score})
        logger.debug(
            f"Added ZADD command for {message_id} to {index_redis_key} to pipeline with score {index_score}."
        )

        pipeline.set(message_name, json.dumps(saved_message.__dict__))
        logger.debug(
            f"Added SET command for {message_name} (is_deleted=False) to pipeline."
        )

        pipeline.execute()
    except Exception as e:
        logger.error(
            f"Failed to save and index Google Chat message: {message_name} in Redis via pipeline: {e}"
        )
        raise


def _handle_update_message(sender_ldap: str, message: dict):
    """
    Handle an UPDATED Google Chat message by appending new text content
    to the existing message stored in Redis.

    This function retrieves the existing message data from Redis using
    the message name as the key, verifies the 'text' field is a list,
    appends the new text with its creation time, and saves the updated
    message back to Redis.

    Args:
        sender_ldap (str): The LDAP identifier of the message sender.
        message (dict): A dictionary containing message data.

    Raises:
        ValueError: If Redis client creation fails or no saved data is found for the message.
        TypeError: If the existing 'text' field in the saved message is not a list.
        Exception: For any errors encountered while saving the updated message back to Redis.
    """
    message_name = message.get("name")
    client_redis = RedisClientFactory().create_redis_client()
    if not client_redis:
        raise ValueError(
            "Failed to create Redis client when updating new Google Chat message."
        )
    saved_data = client_redis.get(message_name)
    if not saved_data:
        raise ValueError(f"No saved data found for message {message_name}.")
    saved_message = json.loads(saved_data)
    create_time = message.get("lastUpdateTime")
    new_text = {
        "value": message.get("text"),
        "createTime": create_time,
    }
    if not isinstance(saved_message.get("text"), list):
        raise TypeError(
            "Attempted to update a database record that appears inconsistent: "
            "'text' field is expected to be a list but found "
            f"{type(saved_message.get('text'))}. Redis key: '{message_name}'."
        )
    saved_message["text"].append(new_text)

    try:
        client_redis.set(message_name, json.dumps(saved_message))
        logger.info(
            f"Google Chat message {message_name} updated in Redis successfully."
        )
    except Exception as e:
        logger.error(
            f"Failed to update Google Chat message details: {message_name} in Redis: {e}"
        )
        raise


def _handle_delete_message(message: dict):
    """
    Handle DELETED message type by marking the message as deleted and updating Redis indexes accordingly.

    This function performs the following steps:
    - Retrieves the message from Redis using the message name.
    - Marks the message's 'is_deleted' flag as True.
    - Removes the message ID from the active (created) messages sorted set.
    - Adds the message ID to the deleted messages sorted set, preserving its original score.
    - Uses a Redis pipeline to atomically update the message data and modify the sorted sets.

    Args:
        message (dict): A dictionary representing the message to be deleted. Must include the "name" key.

    Raises:
        ValueError: If Redis client creation fails or the message does not exist in Redis.
        Exception: If any Redis operation (set, zadd, zrem, pipeline execution) fails.

    Logs relevant information and errors during processing.
    """
    message_name = message.get("name")
    client_redis = RedisClientFactory().create_redis_client()
    if not client_redis:
        raise ValueError(
            "Failed to create Redis client when updating new Google Chat message."
        )
    _, space_id, _, message_id = message_name.split("/")

    saved_data = client_redis.get(message_name)
    if not saved_data:
        raise ValueError(f"Attempted to delete non-existent message {message_name}.")

    saved_message = json.loads(saved_data)
    sender_ldap = saved_message.get("sender")
    index_redis_key = CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
        space_id=space_id, sender_ldap=sender_ldap
    )
    deleted_index_redis_key = DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
        space_id=space_id, sender_ldap=sender_ldap
    )
    score = client_redis.zscore(index_redis_key, message_id)

    saved_message["is_deleted"] = True
    try:
        pipeline = client_redis.pipeline()

        pipeline.set(message_name, json.dumps(saved_message))
        logger.debug(
            f"Added SET command for {message_name} (is_deleted=True) to pipeline."
        )

        pipeline.zrem(index_redis_key, message_id)
        logger.debug(
            f"Added ZREM command for {message_id} from {index_redis_key} to pipeline."
        )

        pipeline.zadd(deleted_index_redis_key, {message_id: score})
        logger.debug(
            f"Added ZADD command for {message_id} to {deleted_index_redis_key} to pipeline with score {score}."
        )

        pipeline.execute()

    except Exception as e:
        logger.error(
            f"Failed to process Google Chat message deletion for {message_name} in Redis via pipeline: {e}"
        )
        raise


def store_messages(sender_ldap: str, message: dict, message_type: GoogleChatEventType):
    """
    Stores, updates, or deletes messages in a Redis database.

    This function stores two types of data in Redis for each message:
    an index (for sorting and lookup) and the message details (as JSON).

    Args:
        sender_ldap (str): The LDAP identifier of the message sender.
        message (dict): A dictionary containing message data. Must include the "name" key within the "message" sub-dictionary.
            The structure of the "message" sub-dictionary varies depending on the message_type:

            -   **created**:
                ```json
                {
                    "name": "spaces/{space_id}/messages/{message_id}",
                    "sender": {
                        "name": "users/{user_id}",
                        "type": "HUMAN"
                    },
                    "createTime": "YYYY-MM-DDTHH:MM:SS.mmmmmmZ",
                    "text": "{message_text}",
                    "thread": {
                        "name": "spaces/{space_id}/threads/{thread_id}"
                    },
                    "space": {
                        "name": "spaces/{space_id}"
                    },
                    "argumentText": "{message_text}",
                    "formattedText": "{message_text}",
                    "attachment": [
                            {
                                "name": "spaces/{space_id}/messages/{message_id}/attachments/{attachment_id}",
                                "contentName": "{file_name}",
                                "contentType": "application/vnd.google-apps.document",
                                "driveDataRef": {"driveFileId": "{file_id}"},
                                "source": "DRIVE_FILE"
                            }
                        ]
                }
                ```
            -   **updated**:
                This type shares the same structure as "created", but includes an additional field:
                ```json
                {
                        // ... (same fields as "created")
                    "lastUpdateTime": "2025-04-01T07:37:05.630895Z",
                }
                ```
            -   **deleted**:
                ```json
                {
                    "name": "spaces/{space_id}/messages/{message_id}",
                    "createTime": "YYYY-MM-DDTHH:MM:SS.mmmmmmZ",
                    "deletionMetadata": {
                        "deletionType": "CREATOR"
                    }
                }
                ```
        message_type (str): The message type, which can be "created", "updated", or "deleted".

    Raises:
        ValueError: If the message format is incorrect.

    Returns:
        None

    Index (Sorted Set): Stored in a Redis sorted set with the following details:
        Key: google:chat:created:{sender_ldap}:{space_id}
        Member: {message_id}
        Score: The Unix timestamp (float) derived from createTime (e.g., 1743667850.991039 for "2025-04-02T09:10:50.991039Z").
    Deleted Index (Sorted Set):
        Key: google:chat:deleted:{sender_ldap}:{space_id}
        // ... (same fields as "created")

    Stored Message Details Format:
        The message is stored in Redis as a JSON-serialized StoredMessage:
    ```json
    {
        "spaces/{space_id}/messages/{message_id}":
        {
            "sender": "{sender_ldap}",
            "threadId": "{thread_id}",
            "text": [
                {
                    "value": "{message_text}",
                    "createTime": "YYYY-MM-DDTHH:MM:SS.mmmmmmZ"
                }
            ],
            "deleted": false,
            "attachment": [
                {
                    "name": "spaces/{space_id}/messages/{message_id}/attachments/{attachment_id}",
                    "contentName": "{file_name}",
                    "contentType": "application/vnd.google-apps.document",
                    "driveDataRef": {"driveFileId": "{file_id}"},
                    "source": "DRIVE_FILE"
                }
            ]
        }
    }
    ```
    """
    message_name = message.get("name")
    if not message_name:
        raise ValueError("Invalid Google Chat message format: missing 'name' field.")
    if message_type == GoogleChatEventType.CREATED.value and sender_ldap:
        _handle_create_message(sender_ldap, message)
    elif message_type == GoogleChatEventType.UPDATED.value and sender_ldap:
        _handle_update_message(sender_ldap, message)
    elif message_type == GoogleChatEventType.DELETED.value:
        _handle_delete_message(message)
    else:
        logger.warning(
            f"Ignored message. message_type={message_type}, sender_ldap={sender_ldap}, message_name={message.get('name')}"
        )
