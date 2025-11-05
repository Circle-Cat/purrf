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
            "thread_id": self.thread_id,
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

    def _get_json_from_redis(self, key: str) -> dict | None:
        """
        Fetch and deserialize a JSON value from Redis.
        Args:
            key (str): Redis key.
        Returns:
            dict | None: Parsed JSON object, or None if the key does not exist.
        Raises:
            json.JSONDecodeError: If the stored value is not valid JSON.
        """
        raw = self.redis_client.get(key)
        if not raw:
            return None
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def store_messages(
        self,
        ldaps_dict: dict,
        batch_messages: list[dict],
        message_type: GoogleChatEventType,
    ) -> None:
        """
        Processes a batch of Google Chat messages and persists their state in Redis.

        Depending on the event type, this method:
          - **CREATED / BATCH_CREATED:** Inserts new message records.
          - **UPDATED / BATCH_UPDATED:** Updates existing message entries.
          - **DELETED / BATCH_DELETED:** Marks messages as deleted.
          - Ignores unsupported message types.

        Each processed message is stored in Redis using:
          1. **Sorted Set Index:** For chronological lookup and ordering by `createTime`.
          2. **Message Hash/JSON Object:** For full message content and metadata.

        Args:
            ldaps_dict (dict):
                Mapping of Google Chat user resource names (e.g., `"users/{user_id}"`)
                to LDAP identifiers. Required for CREATED and BATCH_CREATED types.
            batch_messages (list[dict]):
                A list of raw event payloads, each containing a `"message"` key
                structured according to the Google Chat API event type.
                Example (CREATED message):
                ```json
                {
                    "message": {
                        "name": "spaces/{space_id}/messages/{message_id}",
                        "sender": {"name": "users/{user_id}", "type": "HUMAN"},
                        "createTime": "2025-04-02T09:10:50.991039Z",
                        "text": "Hello world",
                        "space": {"name": "spaces/{space_id}"},
                        "thread": {"name": "spaces/{space_id}/threads/{thread_id}"}
                    }
                }
                ```
            message_type (GoogleChatEventType):
                The event type defining how messages are processed. Must be one of:
                - `CREATED`, `BATCH_CREATED`
                - `UPDATED`, `BATCH_UPDATED`
                - `DELETED`, `BATCH_DELETED`

        Raises:
            ValueError:
                If `ldaps_dict` is missing for creation events or if message format is invalid.
            RuntimeError:
                If Redis pipeline execution fails after retries.

        Redis Storage Layout:
            - **Created Message Index:**
              ```
              Key:   google:chat:created:{sender_ldap}:{space_id}
              Member: {message_id}
              Score:  <createTime as Unix timestamp>
              ```
            - **Deleted Message Index:**
              ```
              Key:   google:chat:deleted:{sender_ldap}:{space_id}
              Member: {message_id}
              Score:  <createTime as Unix timestamp>
              ```
            - **Stored Message Record:**
              ```
              Key:   google:chat:message:{space_id}:{message_id}
              Value: {
                  "sender": "{sender_ldap}",
                  "thread_id": "{thread_id}",
                  "text": [
                      {"value": "{message_text}", "createTime": "..."}
                  ],
                  "is_deleted": false,
                  "attachments": [...]
              }
              ```

        Behavior:
            - Messages from external accounts (no matching LDAP) are skipped.
            - Redis operations are batched via pipeline for atomic efficiency.
            - Pipeline execution is retried on transient Redis errors.

        Returns:
            None
        """

        if not batch_messages:
            self.logger.debug("No Google Chat messages to store.")
            return

        if GoogleChatEventType.CREATED == message_type and not ldaps_dict:
            raise ValueError(
                f"Missing ldaps_dict for batch message type: {message_type}"
            )

        pipeline = self.redis_client.pipeline()
        if message_type in (
            GoogleChatEventType.CREATED,
            GoogleChatEventType.BATCH_CREATED,
        ):
            for message in batch_messages:
                message_info = message.get("message")
                sender_ldap = ldaps_dict.get(
                    message_info.get("sender", {}).get("name", "")
                )
                if not sender_ldap:
                    self.logger.info(
                        "Skip external account sent Google Chat message: %s",
                        message_info.get("name", ""),
                    )
                    continue
                self._handle_created_message(pipeline, message_info, sender_ldap)
        elif message_type in (
            GoogleChatEventType.UPDATED,
            GoogleChatEventType.BATCH_UPDATED,
        ):
            for message in batch_messages:
                message_info = message.get("message")
                self._handle_update_message(pipeline, message_info)
        elif message_type in (
            GoogleChatEventType.DELETED,
            GoogleChatEventType.BATCH_DELETED,
        ):
            for message in batch_messages:
                message_info = message.get("message")
                self._handle_deleted_message(pipeline, message_info)
        else:
            self.logger.warning(
                "Ignored batche messages. message_type=%s",
                message_type,
            )
            return

        try:
            self.retry_utils.get_retry_on_transient(pipeline.execute)
        except Exception as e:
            self.logger.error(
                "Redis pipeline failed for sync Google Chat real time messages, error: %s",
                e,
                exc_info=True,
            )
            raise RuntimeError(
                "Redis pipeline failed for sync Google Chat real time messages"
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

    def _handle_update_message(self, pipeline, message: dict) -> None:
        """
        Updates an existing Google Chat message in Redis with new text content.

        This method handles "UPDATED" message events by retrieving the existing
        stored message from Redis, appending the new text entry (with timestamp)
        to its `text` history, and saving the updated message back.

        Args:
            pipeline (redis.client.Pipeline):
                Redis pipeline instance for atomic batched operations.
            message (dict):
                A dictionary representing the updated message payload, typically
                containing at least:
                ```json
                {
                    "name": "spaces/{space_id}/messages/{message_id}",
                    "text": "Updated content",
                    "lastUpdateTime": "2025-04-01T07:37:05.630895Z"
                }
                ```

        Raises:
            ValueError:
                If `name` or `lastUpdateTime` is missing in the payload,
                or if no stored message is found for the given name.
            TypeError:
                If the existing message's `text` field is not a list.
            Exception:
                For unexpected Redis serialization or storage failures.

        Redis Behavior:
            - Fetches the existing message via `_get_json_from_redis(name)`.
            - Appends a new `TextContent` entry:
              ```
              {"value": message["text"], "createTime": message["lastUpdateTime"]}
              ```
            - Stores the updated message JSON back to Redis using:
              ```
              SET {name} <serialized_message_json>
              ```

        Returns:
            None
        """
        name = message.get("name")
        last_update_time = message.get("lastUpdateTime")
        if not name or not last_update_time:
            raise ValueError("Invalid updated message payload.")

        saved = self._get_json_from_redis(name)
        if not saved:
            self.logger.warning(
                "Attempted to update non-existent message: %s. "
                "This might indicate an external account message or data inconsistency. Skipping updated.",
                name,
            )
            return

        saved_message = StoredGoogleChatMessage(
            sender=saved.get("sender"),
            thread_id=saved.get("thread_id"),
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

        pipeline.set(name, json.dumps(saved_message.to_dict()))
        self.logger.debug("SET %s updated", name)

    def _handle_deleted_message(self, pipeline, message: dict) -> None:
        """
        Marks an existing Google Chat message as deleted in Redis and updates related indexes.

        This method handles **DELETED** or **BATCH_DELETED** Google Chat events.
        It retrieves the stored message from Redis, marks it as deleted, removes it from
        the "created" index, and adds it to the "deleted" index while preserving the original timestamp score.

        Args:
            pipeline (redis.client.Pipeline):
                Redis pipeline instance used for atomic batched operations.
            message (dict):
                The deletion payload from a Google Chat event.
                Must include:
                - `name` (str): Message resource name,
                  formatted as `"spaces/{space_id}/messages/{message_id}"`.

        Raises:
            ValueError:
                - If the message payload lacks required fields or has a malformed `name`.
                - If Redis data is inconsistent (e.g., message not found in the created index).
                - If the stored message record is corrupt or missing required metadata.
            Exception:
                For unexpected Redis operation failures while queuing commands.

        Redis Behavior:
            1. **Retrieve** existing message JSON via `_get_json_from_redis(name)`.
            2. **Skip if already deleted** —
               If the stored record contains `"is_deleted": true`, the method logs and returns early.
               This makes the operation **idempotent**, allowing safe handling of duplicate delete events
               (e.g., within batch deletion processing).
            3. **Mark** message as deleted:
                ```json
                { "is_deleted": true }
                ```
            4. **Update Indexes**:
                - Remove from active messages:
                  ```
                  ZREM google:chat:created:{sender_ldap}:{space_id} {message_id}
                  ```
                - Add to deleted index (retain timestamp score):
                  ```
                  ZADD google:chat:deleted:{sender_ldap}:{space_id} {message_id} <original_score>
                  ```
            5. **Save** updated message object back to Redis:
                ```
                SET spaces/{space_id}/messages/{message_id} <updated_json>
                ```

        Notes:
            - The pipeline is *not executed* within this method; the caller is responsible for execution.
            - This method is **idempotent**: if a message was already deleted, it is safely ignored.
              This is especially important when processing *BATCH_DELETED* events,
              where the same message might appear multiple times.

        Side Effects:
            - Modifies Redis keys and indexes associated with the message.
            - Logs all Redis operations at DEBUG level.

        Returns:
            None
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
        if not saved:
            self.logger.warning(
                "Attempted to delete non-existent message: %s. "
                "This might indicate an external account message or data inconsistency. Skipping deleted.",
                name,
            )
            return

        if saved.get("is_deleted"):
            self.logger.info("Skip already-deleted message: %s", name)
            return

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
