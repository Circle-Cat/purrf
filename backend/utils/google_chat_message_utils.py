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

    def __init__(self, logger, redis_client, retry_utils):
        """
        Args:
            logger: logger with debug/info/warning/error
            redis_client: redis client with get/set/zadd/zrem/zscore/pipeline
            retry_utils: exposes get_retry_on_transient(callable_or_fn)
        """
        self.logger = logger
        self.redis_client = redis_client
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

        Depending on the event type, this method either:
            - Stores a newly created message,
            - Updates an existing message with new fields,
            - Marks a message as deleted.

        Each message is stored in Redis in two ways:
            1. **Index (Sorted Set):** for efficient lookup and sorting.
            2. **Message Details (Hash/JSON):** full serialized message content.

        Args:
            sender_ldap (str | None): The LDAP identifier of the message sender.
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

        if (
            message_type in (GoogleChatEventType.CREATED, GoogleChatEventType.UPDATED)
            and not sender_ldap
        ):
            raise ValueError(
                f"Missing sender_ldap for message type: {message_type}, message name: {message.get('name')}"
            )

        pipeline = None
        if GoogleChatEventType.CREATED == message_type:
            pipeline = self.redis_client.pipeline()
            self._handle_created_message(pipeline, message, sender_ldap)
        elif GoogleChatEventType.UPDATED == message_type:
            self._handle_update_message(message)
        elif GoogleChatEventType.DELETED == message_type:
            pipeline = self.redis_client.pipeline()
            self._handle_deleted_message(pipeline, message)
        else:
            self.logger.warning(
                "Ignored message. message_type=%s, sender_ldap=%s, name=%s",
                message_type,
                sender_ldap,
                message.get("name"),
            )
            return

        if pipeline:
            try:
                self.retry_utils.get_retry_on_transient(pipeline.execute)
            except Exception as e:
                self.logger.error(
                    "Redis pipeline failed for %s: %s",
                    message.get("name"),
                    e,
                    exc_info=True,
                )
                raise RuntimeError(
                    f"Redis pipeline failed for {message.get('name')}"
                ) from e

    def _handle_created_message(
        self, pipeline, message: dict, sender_ldap: str
    ) -> None:
        """
        Queue Redis commands for a "CREATED" Google Chat message into the provided pipeline.

        This method extracts metadata from the message payload, builds a
        `StoredGoogleChatMessage`, and queues Redis operations into the
        provided pipeline. Two things are stored:
        1. The message ID is added to a sorted set (for chronological lookup).
        2. The serialized message details are stored under its Redis key.

        Note:
            The pipeline is not executed here. It must be executed by the caller.

        Args:
            pipeline: A Redis pipeline used for batched atomic operations.
            message (dict): The Google Chat message payload.
            sender_ldap (str): LDAP identifier of the message sender.

        Raises:
            ValueError: If the message payload is missing required fields or
                contains malformed "name" or "thread.name".
            Exception: If queuing operations into the Redis pipeline fails.

        Returns:
            None

        Redis Storage:
            - Sorted Set index:
                Key: "google:chat:created:{sender_ldap}:{space_id}"
                Member: "{message_id}"
                Score:  timestamp from "createTime"
            - Message details:
                Key:   "spaces/{space_id}/messages/{message_id}"
                Value: JSON-serialized `StoredGoogleChatMessage`
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

        pipeline.zadd(created_key, {message_id: index_score})
        self.logger.debug("ZADD %s {%s: %s}", created_key, message_id, index_score)

        pipeline.set(name, json.dumps(stored.to_dict()))
        self.logger.debug("SET %s created", name)

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

    def _handle_deleted_message(self, pipeline, message: dict) -> None:
        """
        Queue Redis commands to mark a Google Chat message as deleted.

        This method performs the following actions using the provided pipeline:
        1. Retrieves the existing message from Redis by its key.
        2. Marks the 'is_deleted' flag as True.
        3. Removes the message ID from the active (created) messages sorted set.
        4. Adds the message ID to the deleted messages sorted set, preserving its original score.

        Note:
            The pipeline is not executed here. Execution must be handled by the caller.

        Args:
            pipeline: A Redis pipeline used for batched atomic operations.
            message (dict): The Google Chat message payload to delete.

        Raises:
            ValueError: If the message payload is missing required fields,
                malformed, or inconsistent with Redis data.
            Exception: If queuing operations into the Redis pipeline fails.

        Returns:
            None

        Redis Commands Queued:
            - Update message details:
                Key:   "spaces/{space_id}/messages/{message_id}"
                Value: JSON with "is_deleted": True
            - Remove from created index:
                Key: "google:chat:created:{sender_ldap}:{space_id}"
                Member: "{message_id}"
            - Add to deleted index:
                Key: "google:chat:deleted:{sender_ldap}:{space_id}"
                Member: "{message_id}"
                Score: original creation timestamp
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

        pipeline.set(name, json.dumps(saved))
        self.logger.debug("SET %s is_deleted=True", name)

        pipeline.zrem(created_key, message_id)

        self.logger.debug("ZREM %s from %s", message_id, created_key)

        pipeline.zadd(deleted_key, {message_id: float(score)})
        self.logger.debug("ZADD %s {%s: %s}", deleted_key, message_id, score)

    def sync_batch_created_messages(self, messages_list: list, all_ldaps_dict: dict):
        """
        Synchronize a batch of Google Chat "CREATED" messages into Redis using a single pipeline.

        This method queues multiple "CREATED" messages into a Redis pipeline
        for atomic batch insertion. Each message is processed via
        `_handle_created_message`, which only queues the necessary Redis commands.
        The pipeline is executed at the end of the method.

        Args:
            messages_list (list): A list of message object.
            all_ldaps_dict (dict): A list of google user ID to LDAP mapping dict.

        Raises:
            RuntimeError: If execution of the Redis pipeline fails.

        Returns:
            None

        Redis Storage:
            For each message, the following commands are queued in the pipeline:
            - **Sorted Set Index**:
                Key: "google:chat:created:{sender_ldap}:{space_id}"
                Member: message_id
                Score: Unix timestamp from createTime
            - **Message Details**:
                Key: "spaces/{space_id}/messages/{message_id}"
                Value: JSON-serialized StoredGoogleChatMessage
        """
        if not all_ldaps_dict:
            raise ValueError("No Google user ID to LDAP mapping provided.")
        if not messages_list:
            raise ValueError("No Google chat messages list provided.")

        pipeline = self.redis_client.pipeline()

        for message_data in messages_list:
            _, sender_id = message_data.get("sender", {}).get("name").split("/")
            sender_ldap = all_ldaps_dict.get(sender_id, "")
            if not sender_ldap:
                self.logger.debug(
                    "No LDAP found for sender_id=%s, external account", sender_id
                )
                continue

            self._handle_created_message(
                pipeline=pipeline, message=message_data, sender_ldap=sender_ldap
            )

        try:
            self.retry_utils.get_retry_on_transient(pipeline.execute)
        except Exception as e:
            self.logger.error(
                "Redis pipeline failed for batch sync: %s", e, exc_info=True
            )
            raise RuntimeError("Redis pipeline failed for batch sync") from e
