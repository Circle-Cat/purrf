from redis_dal.redis_client_factory import RedisClientFactory
from datetime import datetime
from tools.log.logger import setup_logger
import logging
import json
from redis_dal.constants import (
    TYPE_CREATE,
    TYPE_UPDATE,
    TYPE_DELETE,
    MESSAGE,
    NAME,
    MESSAGE_SENDER,
    CREATE_TIME,
    MESSAGE_TEXT,
    MESSAGE_THREAD,
    MESSAGE_SPACE,
    MESSAGE_LAST_UPDATE_TIME,
    MESSAGE_DELETION_METADATA,
    MESSAGE_DELETION_TYPE,
    VALUE,
    MESSAGE_THREAD_ID,
    CHAT_INDEX_KEY_FORMAT,
    MESSAGE_ATTACHMENT,
)
from typing import List, Dict, Optional
from dataclasses import dataclass


setup_logger()


@dataclass
class StoredMessage:
    sender: str
    threadId: Optional[str]
    text: List[Dict[str, str]]
    deleted: bool
    attachment: List[Dict[str, str]]


def store_messages(sender_ldap, message, message_type):
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
        Exception: If Redis operations fail or the message format is incorrect.

    Returns:
        None

    Index (Sorted Set): Stored in a Redis sorted set with the following details:
        Key: {space_id}/{sender_ldap}
        Member: {"name": "spaces/{space_id}/messages/{message_id}"}
        Score: The Unix timestamp (float) derived from createTime (e.g., 1743667850.991039 for "2025-04-02T09:10:50.991039Z").

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
    try:
        client_redis = RedisClientFactory().create_redis_client()
        message_name = message.get(NAME)
        if not message_name:
            logging.warning(
                "Message name not found in the input message. Skipping processing."
            )
            return

        _, space_id, _, message_id = message_name.split("/")
        logging.debug(
            f"Parsed message name: space_id={space_id}, message_id={message_id}"
        )

        if message_type == TYPE_CREATE and sender_ldap:
            create_time = message.get(CREATE_TIME)
            index_score = datetime.fromisoformat(create_time).timestamp()
            index_redis_member = {NAME: message_name}
            index_redis_key = CHAT_INDEX_KEY_FORMAT.format(
                space_id=space_id, sender_ldap=sender_ldap
            )
            client_redis.zadd(index_redis_key, {str(index_redis_member): index_score})
            logging.info(
                f"Message created and added to Redis sorted set: {index_redis_key}"
            )

            thread_name = message.get(MESSAGE_THREAD, {}).get(NAME, "")
            _, _, _, thread_id = thread_name.split("/")
            logging.debug(f"Parsed thread name: thread_id={thread_id}")

            text_content = {VALUE: message.get(MESSAGE_TEXT), CREATE_TIME: create_time}
            stored_message = StoredMessage(
                sender=sender_ldap,
                threadId=thread_id,
                text=[text_content],
                deleted=False,
                attachment=message.get(MESSAGE_ATTACHMENT),
            )
            client_redis.set(message_name, json.dumps(stored_message.__dict__))
            logging.info(f"Message created and stored in Redis: {message_name}")

        elif message_type == TYPE_UPDATE and sender_ldap:
            stored_data = client_redis.get(message_name)
            if not stored_data:
                logging.warning(
                    f"No stored data found for message {message_name}. Update skipped."
                )
                return
            stored_message = json.loads(stored_data)
            create_time = message.get(MESSAGE_LAST_UPDATE_TIME)
            new_text = {
                VALUE: message.get(MESSAGE_TEXT),
                CREATE_TIME: create_time,
            }
            stored_message[MESSAGE_TEXT].append(new_text)
            client_redis.set(message_name, json.dumps(stored_message))
            logging.info(f"Message updated in Redis: {message_name}")

        elif message_type == TYPE_DELETE:
            stored_data = client_redis.get(message_name)
            if not stored_data:
                logging.warning(
                    f"Attempted to deleted non-existent message {message_name}. Delete skipped."
                )
                return
            stored_message = json.loads(stored_data)
            sender_ldap_from_store = stored_message.get("sender")
            index_redis_key = CHAT_INDEX_KEY_FORMAT.format(
                space_id=space_id, sender_ldap=sender_ldap_from_store
            )
            index_member = {NAME: message_name}
            client_redis.zrem(index_redis_key, str(index_member))
            logging.info(f"Message deleted from Redis sorted set: {index_redis_key}")

            stored_message[TYPE_DELETE] = True
            client_redis.set(message_name, json.dumps(stored_message))
            logging.info(f"Message deleted and updated in Redis: {message_name}")

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
