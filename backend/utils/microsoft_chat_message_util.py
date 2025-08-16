import re
import json
from dataclasses import dataclass
from backend.common.constants import (
    MicrosoftChatMessagesChangeType,
    MICROSOFT_CHAT_MESSAGES_INDEX_KEY,
    MICROSOFT_CHAT_MESSAGES_DETAILS_KEY,
    MicrosoftChatMessageAttachmentType,
    MicrosoftChatMessageType,
)


@dataclass
class TextContent:
    value: str
    create_time: str

    def to_dict(self) -> dict:
        """
        Converts the TextContent object into a dictionary format suitable for JSON serialization.
        """
        return {
            "value": self.value,
            "create_time": self.create_time,
        }


@dataclass
class StoredMicrosoftChatMessage:
    sender: str
    text: list[TextContent]
    reply_to: str | None = None
    attachment: list[str] = None

    def to_dict(self) -> dict:
        """
        Converts the StoredMicrosoftChatMessage object into a dictionary format suitable for JSON serialization.
        This method handles the conversion of nested TextContent objects.
        """
        return {
            "sender": self.sender,
            "text": [tc.to_dict() for tc in self.text] if self.text else [],
            "reply_to": self.reply_to,
            "attachment": list(self.attachment) if self.attachment else [],
        }


class MicrosoftChatMessageUtil:
    """
    Synchronizes chat messages between Microsoft Graph and Redis.
    Handles real-time updates and historical data synchronization.
    """

    def __init__(
        self,
        logger,
        redis_client,
        microsoft_service,
        date_time_util,
        retry_utils,
    ):
        """
        Initializes the MicrosoftChatMessageUtil with necessary clients and logger.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            microsoft_service: The MicrosoftService instance.
            date_time_util: A DateTimeUtil for date and time operations.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.microsoft_service = microsoft_service
        self.date_time_util = date_time_util
        self.retry_utils = retry_utils

    def _process_attachments(
        self, attachments: list, message_id: str
    ) -> tuple[list, str | None]:
        """
        Processes the attachments of a single chat message to extract file URLs and
        the ID of a message to reply to.

        For each attachment in the message:
        - If it is a file reference, its content URL is collected.
        - If it is a message reference, its ID is captured for replies.
        - Other types are ignored and logged as warnings.

        Args:
            attachments (list): A list of attachment objects. Each attachment object
                                is expected to have 'content_type', 'content_url', and 'id' attributes.
                                Can be None or empty.
            message_id (str): The ID of the current message being processed. Used for logging.

        Returns:
            tuple: A tuple containing:
                - list: A list of content URLs for file attachments. Empty if no valid file attachments exist.
                - str or None: The ID of the message to reply to, if a message reference
                                attachment was found. Otherwise, None.
        """
        if not attachments:
            self.logger.warning("No attachments found for message %s", message_id)
            return [], None

        processed_attachment = []
        reply_to_message_id = None
        for attachment in attachments:
            content_type = attachment.content_type
            if MicrosoftChatMessageAttachmentType.REFERENCE_LINK.value == content_type:
                processed_attachment.append(attachment.content_url)
            elif (
                MicrosoftChatMessageAttachmentType.MESSAGE_REFERENCE.value
                == content_type
            ):
                reply_to_message_id = attachment.id
            else:
                attachment_id = attachment.id
                self.logger.warning(
                    f"Skipped attachment. message_id={message_id}, attachment_id={attachment_id}"
                )
        return processed_attachment, reply_to_message_id

    def _handle_deleted_message(
        self, message_id: str, sender_ldap: str, score: float, pipeline
    ) -> None:
        """
        Processes a deleted message by removing it from the 'created' index
        and adding it to the 'deleted' index in Redis.

        Args:
            message_id (str): The unique identifier of the message that has been deleted.
            sender_ldap (str): The LDAP identifier of the sender associated with the message.
                            This is used to construct Redis keys.
            score (float): The score associated with the message, which is its creation timestamp.
                    This score is preserved when moving the message to the deleted index.
            pipeline: A Redis pipeline object used for efficient batch operations.
                    Expected to have `zrem` and `zadd` methods.

        Raises:
            ValueError: If `message_id`, `sender_ldap`, `score`, or `pipeline` is
                        None or empty/invalid.
        """
        if not message_id:
            self.logger.error("Input validation failed: message_id is None.")
            raise ValueError("message_id is required.")
        if not sender_ldap:
            self.logger.error("Input validation failed: sender_ldap is empty.")
            raise ValueError("sender_ldap is required.")
        if not score:
            self.logger.error("Input validation failed: score is empty.")
            raise ValueError("Sorted Set score is required.")
        if not pipeline:
            self.logger.error("Input validation failed: pipeline object is None.")
            raise ValueError("Redis pipeline object is required.")

        created_index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.CREATED.value,
            sender_ldap=sender_ldap,
        )
        deleted_index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.DELETED.value,
            sender_ldap=sender_ldap,
        )

        pipeline.zrem(created_index_redis_key, message_id)
        self.logger.debug(
            f"Added ZREM command for {message_id} from {created_index_redis_key} to pipeline."
        )

        pipeline.zadd(deleted_index_redis_key, {message_id: score})
        self.logger.debug(
            f"Added ZADD command for {message_id} to {deleted_index_redis_key} to pipeline with score {score}."
        )

    def _handle_created_messages(
        self, message: str, sender_ldap: str, pipeline
    ) -> None:
        """
        Processes a newly created message and stores its details in Redis.
        Extracts message content, sender information, attachment URLs, and reply-to
        message ID. Formats the creation timestamp and then uses a Redis pipeline
        to store the message's index (ranked by time) and its detailed information.

        Args:
            message: The microsoft.graph.chatMessage object.
                    https://learn.microsoft.com/zh-cn/graph/api/resources/chatmessage?view=graph-rest-1.0
            sender_ldap (str): The LDAP identifier of the message sender.
            pipeline: A Redis pipeline object used for efficient batch operations.

        Raises:
            ValueError: If `message`, `sender_ldap`, or `pipeline` is None or empty.
            AttributeError: If message or its sub-attributes are missing or malformed.
            ValueError: If `created_date_time` is not a valid datetime or formatting fails.
        """
        if not message:
            self.logger.error("Input validation failed: message object is None.")
            raise ValueError("message object is required.")
        if not sender_ldap:
            self.logger.error("Input validation failed: sender_ldap is empty.")
            raise ValueError("sender_ldap is required.")
        if not pipeline:
            self.logger.error("Input validation failed: pipeline object is None.")
            raise ValueError("Redis pipeline object is required.")

        message_id = message.id
        created_date_time = message.created_date_time
        body = message.body
        content = body.content if body else ""
        attachments = message.attachments
        process_attachment, reply_to_message_id = self._process_attachments(
            attachments, message_id
        )
        formatted_create_date_time = self.date_time_util.format_datetime_to_iso_utc_z(
            created_date_time
        )
        text_content = TextContent(
            value=content, create_time=formatted_create_date_time
        )
        message_detail = StoredMicrosoftChatMessage(
            sender=sender_ldap,
            text=[text_content],
            attachment=process_attachment if process_attachment else [],
            reply_to=reply_to_message_id,
        )
        detail_key = MICROSOFT_CHAT_MESSAGES_DETAILS_KEY.format(message_id=message_id)
        index_score = created_date_time.timestamp()
        index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.CREATED.value,
            sender_ldap=sender_ldap,
        )

        pipeline.zadd(index_redis_key, {message_id: index_score})
        self.logger.debug(
            f"Added message {message_id} to {index_redis_key} with score {index_score}"
        )

        pipeline.set(detail_key, json.dumps(message_detail.to_dict()))
        self.logger.debug(f"Saved message details for {message_id} to {detail_key}")

    def _handle_update_message(self, message: str, sender_ldap: str, pipeline) -> None:
        """
        Handles an updated chat message. This function is responsible for retrieving
        old message data from Redis, comparing it with new message data, and updating
        the record in Redis. It also manages updating the message's status in Redis
        sorted sets.

        Args:
            message: The microsoft.graph.chatMessage object containing the latest information.
            sender_ldap: The LDAP identifier of the user who sent the message.
            pipeline: A Redis pipeline object for batching Redis commands.

        Raises:
            ValueError: If input parameters are invalid or if data inconsistencies are found.
        """
        if not message:
            self.logger.error("Input validation failed: message object is None.")
            raise ValueError("message object is required.")
        if not sender_ldap:
            self.logger.error("Input validation failed: sender_ldap is empty.")
            raise ValueError("sender_ldap is required.")
        if not pipeline:
            self.logger.error("Input validation failed: pipeline object is None.")
            raise ValueError("Redis pipeline object is required.")

        message_id = message.id
        created_index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.CREATED.value,
            sender_ldap=sender_ldap,
        )
        score = self.redis_client.zscore(created_index_redis_key, message_id)
        if not score:
            deleted_index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
                message_status=MicrosoftChatMessagesChangeType.DELETED.value,
                sender_ldap=sender_ldap,
            )

            score = self.redis_client.zscore(deleted_index_redis_key, message_id)
            if not score:
                self.logger.error(
                    f"Message {message_id} not found in either CREATED or DELETED index for sender {sender_ldap}."
                )
                raise ValueError("Redis data inconsistent: Message not found in index.")
            self.logger.info(
                f"Undoing deletion for message {message_id}. Moving from DELETED to CREATED index."
            )

            pipeline.zrem(deleted_index_redis_key, message_id)
            self.logger.debug(
                f"Added ZREM command for {message_id} from {deleted_index_redis_key} to pipeline."
            )

            pipeline.zadd(created_index_redis_key, {message_id: score})
            self.logger.debug(
                f"Added ZADD command for {message_id} to {created_index_redis_key} to pipeline with score {score}."
            )
        else:
            message_detail_key = MICROSOFT_CHAT_MESSAGES_DETAILS_KEY.format(
                message_id=message_id
            )
            saved_data_json = self.redis_client.get(message_detail_key)
            if not saved_data_json:
                raise ValueError(
                    f"Attempted to update non-existent message {message_detail_key}."
                )
            saved_data = json.loads(saved_data_json)
            saved_message = StoredMicrosoftChatMessage(
                sender=saved_data["sender"],
                text=[TextContent(**t) for t in saved_data.get("text", [])],
                reply_to=saved_data.get("reply_to"),
                attachment=list(saved_data.get("attachment", [])),
            )
            body = message.body
            new_content = body.content if body else ""
            created_date_time = message.last_modified_date_time
            formatted_create_date_time = (
                self.date_time_util.format_datetime_to_iso_utc_z(created_date_time)
            )
            new_content_object = TextContent(
                value=new_content, create_time=formatted_create_date_time
            )
            new_attachments = message.attachments
            previous_attachments = saved_message.attachment
            new_process_attachment_urls, new_reply_to_message_id = (
                self._process_attachments(new_attachments, message_id)
            )
            is_updated = False
            if not saved_message.text or saved_message.text[-1] != new_content_object:
                saved_message.text.append(new_content_object)
                is_updated = True
            for url in new_process_attachment_urls:
                if url not in previous_attachments:
                    saved_message.attachment.append(url)
                    is_updated = True
                else:
                    continue
            if new_reply_to_message_id != saved_message.reply_to:
                saved_message.reply_to = new_reply_to_message_id
                is_updated = True

            if is_updated:
                pipeline.set(message_detail_key, json.dumps(saved_message.to_dict()))
                self.logger.debug(f"Updated message details for {message_id} in Redis.")

    async def sync_near_real_time_message_to_redis(
        self, change_type: MicrosoftChatMessagesChangeType, resource: str
    ):
        """
        Synchronizes a single chat message update (create, update, or delete) from
        Microsoft Graph notifications to Redis in near real-time.

        This asynchronous function parses a resource string to extract `chat_id` and `message_id`.
        It then fetches the latest message details from the Microsoft Graph API. Based on the
        `change_type`, it either handles the message creation, updates its content and metadata
        in Redis, or marks it as deleted in Redis. External messages or those with missing
        information are logged and skipped.

        Args:
            change_type: The type of change notification received (e.g., 'created', 'updated', 'deleted').
                        Expected values are from `MicrosoftChatMessagesChangeType`.
            resource: A string representing the resource that changed. Expected format is
                    "chats('{chat_id}')/messages('{message_id}')".

        Raises:
            ValueError: If the `resource` string format is invalid, if clients (Graph or Redis)
                        cannot be created, or if Redis data is inconsistent.
            RuntimeError: For unexpected errors during processing or Redis pipeline execution.
        """
        if not MicrosoftChatMessagesChangeType.is_supported(change_type):
            raise ValueError(
                "Invalid Microsoft notification: 'change_type' is empty, None, or unsupported."
            )
        if not resource:
            raise ValueError(
                "Invalid Microsoft notification: 'resource' is empty or None."
            )
        pattern = r"chats\('(.+?)'\)/messages\('(.+?)'\)"
        match = re.match(pattern, resource)
        if match:
            chat_id = match.group(1)
            message_id = match.group(2)
        else:
            raise ValueError("Invalid Microsoft notifiction format.")
        message = await self.microsoft_service.get_message_by_id(chat_id, message_id)
        if MicrosoftChatMessageType.Message != message.message_type:
            self.logger.info(f"Skipping message {message_id}: Sent by system.")
            return
        pipeline = self.redis_client.pipeline()
        sender_info = message.from_.user if message.from_ else None
        sender_id = sender_info.id if sender_info else None
        sender_ldap = await self.microsoft_service.get_ldap_by_id(sender_id)
        if not sender_ldap:
            self.logger.warning(
                f"Skipping message {message_id}: Sent by external account."
            )
            return
        if MicrosoftChatMessagesChangeType.DELETED.value == change_type:
            created_index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
                message_status=MicrosoftChatMessagesChangeType.CREATED.value,
                sender_ldap=sender_ldap,
            )
            score = self.redis_client.zscore(created_index_redis_key, message_id)
            if score:
                self._handle_deleted_message(message_id, sender_ldap, score, pipeline)
            else:
                self.logger.warning(
                    f"Message ID {message_id} not found in created index, cannot properly mark as deleted."
                )
                raise ValueError("Redis datat inconsistency.")

        elif MicrosoftChatMessagesChangeType.CREATED.value == change_type:
            self._handle_created_messages(message, sender_ldap, pipeline)

        else:
            self._handle_update_message(message, sender_ldap, pipeline)

        try:
            self.retry_utils.get_retry_on_transient(pipeline.execute)
        except Exception as e:
            self.logger.error(
                f"Failed to execute Redis pipeline for near real-time sync message_id={message_id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to execute Redis pipeline for near real-time sync message_id={message_id}."
            ) from e

    def sync_history_chat_messages_to_redis(
        self, messages: list, all_ldaps: dict
    ) -> tuple[int, int]:
        """
        Synchronizes a list of Microsoft chat messages (history) to Redis.
        This method iterates through a provided list of messages. For each valid,
        non-deleted message, it processes its content, sender information, and attachments.

        It uses the `_handle_created_messages` helper function to prepare and add
        the message data and its index entry to a Redis pipeline.
        Messages that are marked as deleted, lack sender information, or whose senders
        are not found in the provided LDAP mapping are skipped.

        Args:
            messages: A list of microsoft.graph.chatMessage objects.
            all_ldaps: A dictionary mapping sender Microsoft Graph user IDs to their
                    corresponding LDAP identifiers. This mapping is used to determine the
                    sender's LDAP for storing in Redis.

        Returns:
            A tuple containing two integers:
            - The total number of messages successfully processed and added to Redis.
            - The total number of messages skipped due to being deleted, missing sender info,
            or not being present in the LDAP mapping.

        Raises:
            ValueError: If the `messages` list or `all_ldaps` dictionary is empty, or if
                        a Redis client cannot be created.
        """
        if not messages:
            self.logger.debug("No Microsoft chat messages list provided.")
            raise ValueError("No Microsoft chat messages list provided.")
        if not all_ldaps:
            self.logger.debug("No display name LDAP mapping provided.")
            raise ValueError("No display name LDAP mapping provided.")

        pipe = self.redis_client.pipeline()
        total_processed = 0
        total_skipped = 0
        for message in messages:
            message_id = message.id
            if MicrosoftChatMessageType.Message != message.message_type:
                total_skipped += 1
                self.logger.debug(f"Skipping message {message_id}: Sent by system.")
                continue
            if message.deleted_date_time:
                total_skipped += 1
                self.logger.debug(
                    f"Message ID {message.id}: Deleted message, skipping."
                )
                continue
            sender_info = message.from_.user if message.from_ else None
            sender_id = sender_info.id if sender_info else None
            sender_ldap = all_ldaps.get(sender_id)
            if not sender_ldap:
                total_skipped += 1
                self.logger.debug(
                    f"Message ID {message.id}: Sender ID {sender_id} not found in LDAP mapping, sender is not currently in the organization."
                )
                continue

            self._handle_created_messages(message, sender_ldap, pipe)
            total_processed += 1

        self.retry_utils.get_retry_on_transient(pipe.execute)

        self.logger.debug(
            f"Total {total_processed} Microsoft chat messages processed, {total_skipped} messages skipped."
        )

        return total_processed, total_skipped
