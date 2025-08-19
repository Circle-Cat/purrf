import json


class MicrosoftMessageProcessorService:
    """
    Service class responsible for processing Microsoft chat messages.

    This class handles:
    - Pulling messages from Pub/Sub via the provided factory.
    - Processing and transforming Microsoft chat messages using the provided utility.
    - Logging relevant events and errors during message processing.

    Attributes:
        logger: A logging instance.
        pubsub_puller_factory: A PubSubPullerFactory instance.
        microsoft_chat_message_util: A MicrosoftChatMessageUtil instance.
    """

    def __init__(self, logger, pubsub_puller_factory, microsoft_chat_message_util):
        """Initialize the MicrosoftMessageProcessorService."""
        self.logger = logger
        self.pubsub_puller_factory = pubsub_puller_factory
        self.microsoft_chat_message_util = microsoft_chat_message_util

    async def process_data_async(self, message):
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
            await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
                change_type, resource
            )
            message.ack()
        except Exception as e:
            self.logger.error(
                f"Error processing message {message.message_id}: {e}", exc_info=True
            )
            message.nack()

    def pull_microsoft_message(self, project_id: str, subscription_id: str):
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
        puller = self.pubsub_puller_factory.get_puller_instance(
            project_id, subscription_id
        )
        puller.start_pulling_messages(self.process_data_async)
