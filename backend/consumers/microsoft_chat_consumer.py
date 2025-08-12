from backend.utils.microsoft_chat_message_store import sync_near_real_time_message_to_redis
from backend.consumers.pubsub_puller import PubSubPuller
from backend.common.logger import get_logger
import json

logger = get_logger()


async def process_data_async(message):
    """
    Asynchronously process a Pub/Sub message by decoding its data
    and syncing the related Microsoft chat message to Redis.

    Args:
        message: The Pub/Sub message object containing the data.

    Side Effects:
        Acknowledges the message on success, or negatively acknowledges on failure.
    """
    data = json.loads(message.data.decode("utf-8"))
    change_type = data.get("changeType")
    resource = data.get("resource")

    try:
        await sync_near_real_time_message_to_redis(change_type, resource)
        message.ack()
    except Exception as e:
        logger.error(
            f"Error processing message {message.message_id}: {e}", exc_info=True
        )
        message.nack()


def pull_microsoft_message(project_id: str, subscription_id: str):
    """
    Start pulling Microsoft Pub/Sub messages for the given project and subscription,
    processing them using the synchronous wrapper.

    Args:
        project_id (str): Google Cloud project ID (non-empty).
        subscription_id (str): Pub/Sub subscription ID (non-empty).

    Raises:
        ValueError: If either `project_id` or `subscription_id` is empty.
    """
    if not project_id:
        raise ValueError("project_id must be a non-empty string")
    if not subscription_id:
        raise ValueError("subscription_id must be a non-empty string")

    PubSubPuller(project_id, subscription_id).start_pulling_messages(process_data_async)
