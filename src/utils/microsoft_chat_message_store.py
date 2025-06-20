import re
import json
from datetime import datetime
from msgraph.generated.models.chat_message_type import ChatMessageType
from src.common.microsoft_client import MicrosoftClientFactory
from src.common.redis_client import RedisClientFactory
from dataclasses import dataclass, field, asdict
from http import HTTPStatus
from src.common.constants import (
    MicrosoftChatMessagesChangeType,
    MICROSOFT_CHAT_MESSAGES_INDEX_KEY,
    MICROSOFT_CHAT_MESSAGES_DETAILS_KEY,
    MICROSOFT_LDAP_KEY,
    MicrosoftChatMessageAttachmentType,
)
from tenacity import retry, stop_after_attempt, wait_exponential
from src.common.logger import get_logger

logger = get_logger()


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
    attachment: list[str] = field(default_factory=list[str])

    def to_dict(self) -> dict:
        """
        Converts the StoredMicrosoftChatMessage object into a dictionary format suitable for JSON serialization.
        This method handles the conversion of nested TextContent objects.
        """
        data_dict = asdict(self)
        data_dict["text"] = [tc.to_dict() for tc in self.text] if self.text else []
        attachment = self.attachment
        data_dict["attachment"] = list(attachment) if attachment else []

        return data_dict


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    reraise=True,
)
def _execute_request(request):
    return request.execute()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    reraise=True,
)
async def _get_ldap_by_id(id, graph_client):
    """
    Retrieves a user's LDAP identifier using their Microsoft Graph API user ID.

    Fetches user details from Microsoft Graph API and extracts the LDAP
    identifier from the user's email address.

    Args:
        id (str): The Microsoft Graph API user ID (e.g., Object ID) of the user.
        graph_client: An initialized Microsoft Graph API client object.

    Returns:
        str or None: The user's LDAP identifier if found; otherwise None if the user is not found (HTTP 404).

    Raises:
        ValueError:
            - If `graph_client` is not provided.
            - If there's an error calling the Microsoft Graph API to get user info.
    """
    if not graph_client:
        raise ValueError("Microsoft Graph client not provided.")
    try:
        result = await graph_client.users.by_user_id(id).get()
    except Exception as e:
        if (
            hasattr(e, "response_status_code")
            and e.response_status_code == HTTPStatus.NOT_FOUND
        ):
            logger.info(f"User ID '{id}' not found in Microsoft Graph.")
            return None
        raise ValueError(f"Failed to retrieve LDAP for Microsoft user ID {id}.")
    mail = result.mail
    ldap, _ = mail.split("@")
    return ldap


def _format_datetime_to_iso_utc_z(dt_object: datetime) -> str:
    """
    Formats a datetime object into an ISO 8601 string with microseconds
    and 'Z' for UTC timezone.

    Args:
        dt_object (datetime): The datetime object to format.

    Returns:
        str: The formatted ISO 8601 datetime string (e.g., "2023-10-27T10:30:45.123456Z").

    Raises:
        ValueError: If the dt_object is not a valid datetime or if formatting fails.
    """
    if not isinstance(dt_object, datetime):
        raise ValueError("Input must be a datetime object.")
    try:
        return dt_object.isoformat(timespec="microseconds").replace("+00:00", "Z")
    except Exception as e:
        logger.error(f"Failed to format datetime object: {e}", exc_info=True)
        raise ValueError(f"Failed to format datetime object: {dt_object}.")


def _process_attachments(attachments, message_id):
    """
    Processes a list of message attachments to extract file URLs and reply message IDs.

    Iterates through the provided attachments. If an attachment is a file
    reference, its content URL is added to a list. If it's a message reference,
    its ID is captured to be used for replies. Other attachment types are logged
    as warnings.

    Args:
        attachments (list): A list of attachment objects. Each attachment object
                            is expected to have 'content_type', 'content_url', and 'id' attributes.
                            Can be None or empty.
        message_id (str): The ID of the current message being processed. Used for logging.

    Returns:
        tuple: A tuple containing:
               - list: A list of content URLs for file attachments.
               - str or None: The ID of the message to reply to, if a message reference
                              attachment was found. Otherwise, None.
    """
    processed_attachment = []
    reply_to_message_id = None

    for attachment in attachments or []:
        content_type = attachment.content_type
        if content_type == MicrosoftChatMessageAttachmentType.REFERENCE_LINK.value:
            processed_attachment.append(attachment.content_url)

        elif content_type == MicrosoftChatMessageAttachmentType.MESSAGE_REFERENCE.value:
            reply_to_message_id = attachment.id

        else:
            attachment_id = attachment.id
            logger.warning(
                f"Skipped attachment. message_id={message_id}, attachment_id={attachment_id}"
            )
    return processed_attachment, reply_to_message_id


def _handle_deleted_message(message_id, sender_ldap, score, pipeline):
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
        logger.error("Input validation failed: message_id is None.")
        raise ValueError("Message_id is required.")
    if not sender_ldap:
        logger.error("Input validation failed: sender_ldap is empty.")
        raise ValueError("Sender LDAP is required.")
    if not score:
        logger.error("Input validation failed: score is empty.")
        raise ValueError("Sorted Set score is required.")
    if not pipeline:
        logger.error("Input validation failed: pipeline object is None.")
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
    logger.debug(
        f"Added ZREM command for {message_id} from {created_index_redis_key} to pipeline."
    )
    pipeline.zadd(deleted_index_redis_key, {message_id: score})
    logger.debug(
        f"Added ZADD command for {message_id} to {deleted_index_redis_key} to pipeline with score {score}."
    )


def _handle_created_messages(message, sender_ldap, pipeline):
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
        logger.error("Input validation failed: message object is None.")
        raise ValueError("Message object is required.")
    if not sender_ldap:
        logger.error("Input validation failed: sender_ldap is empty.")
        raise ValueError("Sender LDAP is required.")
    if not pipeline:
        logger.error("Input validation failed: pipeline object is None.")
        raise ValueError("Redis pipeline object is required.")

    message_id = message.id
    created_date_time = message.created_date_time
    body = message.body
    content_type = body.content_type if body else None
    content = body.content if body else ""
    attachments = message.attachments

    process_attachment, reply_to_message_id = _process_attachments(
        attachments, message_id
    )
    formatted_create_date_time = _format_datetime_to_iso_utc_z(created_date_time)
    text_content = TextContent(value=content, create_time=formatted_create_date_time)
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
    logger.debug(
        f"Added message {message_id} to {index_redis_key} with score {index_score}"
    )
    pipeline.set(detail_key, json.dumps(message_detail.to_dict()))
    logger.debug(f"Saved message details for {message_id} to {detail_key}")


def _handle_update_message(message, sender_ldap, pipeline, redis_client):
    """
    Handles an updated chat message. This function is responsible for retrieving
    old message data from Redis, comparing it with new message data, and updating
    the record in Redis. It also manages updating the message's status in Redis
    sorted sets.

    Args:
        message: The microsoft.graph.chatMessage object containing the latest information.
        sender_ldap: The LDAP identifier of the user who sent the message.
        pipeline: A Redis pipeline object for batching Redis commands.
        redis_client: The Redis client object.

    Raises:
        ValueError: If input parameters are invalid or if data inconsistencies are found.
    """
    if not message:
        logger.error("Input validation failed: message object is None.")
        raise ValueError("Message object is required.")
    if not sender_ldap:
        logger.error("Input validation failed: sender_ldap is empty.")
        raise ValueError("Sender LDAP is required.")
    if not pipeline:
        logger.error("Input validation failed: pipeline object is None.")
        raise ValueError("Redis pipeline object is required.")
    if not redis_client:
        logger.error("Input validation failed: redis client object is None.")
        raise ValueError("Redis client object is required.")

    message_id = message.id
    created_index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
        message_status=MicrosoftChatMessagesChangeType.CREATED.value,
        sender_ldap=sender_ldap,
    )
    score = redis_client.zscore(created_index_redis_key, message_id)
    if not score:
        deleted_index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.DELETED.value,
            sender_ldap=sender_ldap,
        )
        score = redis_client.zscore(deleted_index_redis_key, message_id)
        if not score:
            logger.error(
                f"Message {message_id} not found in either CREATED or DELETED index for sender {sender_ldap}."
            )
            raise ValueError("Redis data inconsistent: Message not found in index.")
        else:
            logger.info(
                f"Undoing deletion for message {message_id}. Moving from DELETED to CREATED index."
            )
            pipeline.zrem(deleted_index_redis_key, message_id)
            logger.debug(
                f"Added ZREM command for {message_id} from {deleted_index_redis_key} to pipeline."
            )
            pipeline.zadd(created_index_redis_key, {message_id: score})
            logger.debug(
                f"Added ZADD command for {message_id} to {created_index_redis_key} to pipeline with score {score}."
            )
    else:
        message_detail_key = MICROSOFT_CHAT_MESSAGES_DETAILS_KEY.format(
            message_id=message_id
        )
        saved_data_json = redis_client.get(message_detail_key)
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
        formatted_create_date_time = _format_datetime_to_iso_utc_z(created_date_time)
        new_content_object = TextContent(
            value=new_content, create_time=formatted_create_date_time
        )
        new_attachments = message.attachments
        previous_attachments = saved_message.attachment
        new_process_attachment_urls, new_reply_to_message_id = _process_attachments(
            new_attachments, message_id
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
            logger.debug(f"Updated message details for {message_id} in Redis.")


async def sync_near_real_time_message_to_redis(change_type, resource):
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
        raise ValueError("Invalid Microsoft notification: 'resource' is empty or None.")

    pattern = r"chats\('(.+?)'\)/messages\('(.+?)'\)"
    match = re.match(pattern, resource)
    if match:
        chat_id = match.group(1)
        message_id = match.group(2)
    else:
        raise ValueError("Invalid Microsoft notifiction format.")

    graph_client = MicrosoftClientFactory().create_graph_service_client()
    if not graph_client:
        raise ValueError("Microsoft Graph client not created.")

    message = (
        await graph_client.chats.by_chat_id(chat_id)
        .messages.by_chat_message_id(message_id)
        .get()
    )

    if message.message_type != ChatMessageType.Message:
        logger.info(f"Skipping message {message_id}: Sended by system.")
        return
    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")

    pipeline = redis_client.pipeline()
    sender_info = message.from_.user if message.from_ else None
    sender_id = sender_info.id if sender_info else None
    sender_ldap = await _get_ldap_by_id(sender_id, graph_client)
    if not sender_ldap:
        logger.warning(f"Skipping message {message_id}: Sended by external account.")
        return

    if change_type == MicrosoftChatMessagesChangeType.DELETED.value:
        created_index_redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
            message_status=MicrosoftChatMessagesChangeType.CREATED.value,
            sender_ldap=sender_ldap,
        )
        score = redis_client.zscore(created_index_redis_key, message_id)
        if score:
            _handle_deleted_message(message_id, sender_ldap, score, pipeline)
        else:
            logger.warning(
                f"Message ID {message_id} not found in created index, cannot properly mark as deleted."
            )
            raise ValueError("Redis datat inconsistency.")

    elif change_type == MicrosoftChatMessagesChangeType.CREATED.value:
        _handle_created_messages(message, sender_ldap, pipeline)

    else:
        _handle_update_message(message, sender_ldap, pipeline, redis_client)

    try:
        _execute_request(pipeline)
    except Exception as e:
        logger.error(
            f"Failed to execute Redis pipeline for near real-time sync message_id={message_id}: {e}",
            exc_info=True,
        )
        raise RuntimeError(
            f"Failed to execute Redis pipeline for near real-time sync message_id={message_id}."
        )
