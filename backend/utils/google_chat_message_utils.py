import json
from dataclasses import dataclass
from datetime import datetime
from backend.common.constants import (
    GoogleChatEventType,
    CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY,
    DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY,
)


@dataclass
class TextContent:
    value: str | None
    create_time: str

    def to_dict(self) -> dict:
        return {"value": self.value, "createTime": self.create_time}


@dataclass
class StoredGoogleChatMessage:
    sender: str
    thread_id: str
    text: list[TextContent]
    is_deleted: bool
    attachment: list | None = None

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "threadId": self.thread_id,
            "text": [tc.to_dict() for tc in self.text] if self.text else [],
            "is_deleted": self.is_deleted,
            "attachment": list(self.attachment) if self.attachment else [],
        }


class GoogleChatMessagesUtils:
    """
    Synchronizes Google Chat messages and indices in Redis.
    """

    def __init__(self, logger, redis_client, date_time_util, retry_utils):
        """
        Args:
            logger: logger with debug/info/warning/error
            redis_client: redis client with get/set/zadd/zrem/zscore/pipeline
            date_time_util: reserved (optional)
            retry_utils: exposes get_retry_on_transient(callable_or_fn)
        """
        self.logger = logger
        self.redis_client = redis_client
        self.date_time_util = date_time_util
        self.retry_utils = retry_utils

    def _get_json_from_redis(self, key: str) -> dict:
        """
        Fetch and deserialize a JSON value from Redis.
        Args:
            key (str): Redis key.
        Returns:
            dict: Parsed JSON object.
        Raises:
            ValueError: If the key does not exist in Redis.
            json.JSONDecodeError: If the stored value is not valid JSON.
        """
        raw = self.redis_client.get(key)
        if not raw:
            raise ValueError(f"Redis key {key} does not exist.")
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def store_messages(
        self,
        sender_ldap: str | None,
        message: dict,
        message_type: GoogleChatEventType,
    ) -> None:
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
            message_type (GoogleChatEventType): The message type, which can be "created", "updated", or "deleted".
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
        if not message or not message.get("name"):
            raise ValueError("Invalid Google Chat message: missing 'name'.")
        if GoogleChatEventType.CREATED == message_type and sender_ldap:
            self._handle_created_message(message, sender_ldap)
        elif GoogleChatEventType.UPDATED == message_type and sender_ldap:
            self._handle_update_message(message)
        elif GoogleChatEventType.DELETED == message_type:
            self._handle_deleted_message(message)
        else:
            self.logger.warning(
                "Ignored message. message_type=%s, sender_ldap=%s, name=%s",
                message_type,
                sender_ldap,
                message.get("name"),
            )

    def _handle_created_message(self, message: dict, sender_ldap: str) -> None:
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
        name = message.get("name")
        create_time = message.get("createTime")
        if not name or not create_time:
            raise ValueError("Invalid created message payload.")

        try:
            _, space_id, _, message_id = name.split("/")
        except Exception as e:
            self.logger.error("Malformed message name: %s", name)
            raise ValueError("Malformed Google Chat message name.") from e

        thread_name = (message.get("thread") or {}).get("name")
        if not thread_name:
            raise ValueError("Missing thread metadata.")
        try:
            _, _, _, thread_id = thread_name.split("/")
        except Exception as e:
            self.logger.error("Malformed thread name: %s", thread_name)
            raise ValueError("Malformed Google Chat thread name.") from e

        index_score = datetime.fromisoformat(
            create_time.replace("Z", "+00:00")
        ).timestamp()

        created_key = CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
            space_id=space_id, sender_ldap=sender_ldap
        )

        text_content = TextContent(value=message.get("text"), create_time=create_time)
        stored = StoredGoogleChatMessage(
            sender=sender_ldap,
            thread_id=thread_id,
            text=[text_content],
            is_deleted=False,
            attachment=message.get("attachment") or [],
        )

        pipe = self.redis_client.pipeline()
        pipe.zadd(created_key, {message_id: index_score})
        self.logger.debug("ZADD %s {%s: %s}", created_key, message_id, index_score)
        pipe.set(name, json.dumps(stored.to_dict()))
        self.logger.debug("SET %s created", name)

        try:
            self.retry_utils.get_retry_on_transient(pipe.execute)
        except Exception as e:
            self.logger.error(
                "Redis pipeline failed for %s: %s", name, e, exc_info=True
            )
            raise RuntimeError(f"Redis pipeline failed for {name}") from e

    def _handle_update_message(self, message: dict) -> None:
        """
        Handle an UPDATED Google Chat message by appending new text content
        to the existing message stored in Redis.
        This function retrieves the existing message data from Redis using
        the message name as the key, verifies the 'text' field is a list,
        appends the new text with its creation time, and saves the updated
        message back to Redis.
        Args:
            message (dict): A dictionary containing message data.
        Raises:
            ValueError: If Redis client creation fails or no saved data is found for the message.
            TypeError: If the existing 'text' field in the saved message is not a list.
            Exception: For any errors encountered while saving the updated message back to Redis.
        """
        name = message.get("name")
        last_update_time = message.get("lastUpdateTime")
        if not name or not last_update_time:
            raise ValueError("Invalid updated message payload.")

        saved = self._get_json_from_redis(name)

        saved_message = StoredGoogleChatMessage(
            sender=saved.get("sender"),
            thread_id=saved.get("threadId"),
            text=[
                TextContent(value=t.get("value"), create_time=t.get("createTime"))
                for t in (saved.get("text") or [])
            ],
            is_deleted=bool(saved.get("is_deleted")),
            attachment=list(saved.get("attachment") or []),
        )

        saved_message.text.append(
            TextContent(value=message.get("text"), create_time=last_update_time)
        )

        try:
            self.retry_utils.get_retry_on_transient(
                lambda: self.redis_client.set(name, json.dumps(saved_message.to_dict()))
            )
            self.logger.debug("SET %s updated", name)
        except Exception as e:
            self.logger.error(
                "Failed to update Google Chat message details: %s in Redis: %s",
                name,
                e,
                exc_info=True,
            )
            raise

    def _handle_deleted_message(self, message: dict) -> None:
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
        name = message.get("name")
        if not name:
            raise ValueError("Invalid deleted message payload.")
        try:
            _, space_id, _, message_id = name.split("/")
        except Exception as e:
            self.logger.error("Malformed message name: %s", name)
            raise ValueError("Malformed Google Chat message name.") from e

        saved = self._get_json_from_redis(name)

        sender_ldap = saved.get("sender")
        if not sender_ldap:
            raise ValueError("Corrupt saved record: missing 'sender'.")

        created_key = CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
            space_id=space_id, sender_ldap=sender_ldap
        )
        deleted_key = DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
            space_id=space_id, sender_ldap=sender_ldap
        )

        score = self.redis_client.zscore(created_key, message_id)
        if score is None:
            self.logger.error(
                "Redis data inconsistent: message_id=%s not found in CREATED index key=%s "
                "while processing delete for name=%s",
                message_id,
                created_key,
                name,
            )
            raise ValueError(
                "Redis data inconsistent: message not found in CREATED index."
            )

        saved["is_deleted"] = True

        pipe = self.redis_client.pipeline()
        pipe.set(name, json.dumps(saved))
        self.logger.debug("SET %s is_deleted=True", name)
        pipe.zrem(created_key, message_id)
        self.logger.debug("ZREM %s from %s", message_id, created_key)
        pipe.zadd(deleted_key, {message_id: float(score)})
        self.logger.debug("ZADD %s {%s: %s}", deleted_key, message_id, score)

        try:
            self.retry_utils.get_retry_on_transient(pipe.execute)
        except Exception as e:
            self.logger.error(
                "Redis pipeline failed for delete %s: %s", name, e, exc_info=True
            )
            raise RuntimeError(f"Redis pipeline failed for delete {name}") from e
