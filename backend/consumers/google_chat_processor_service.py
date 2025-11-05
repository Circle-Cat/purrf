import json
from backend.common.constants import (
    EXPIRATION_REMINDER_EVENT,
    EVENT_TYPES,
)


class GoogleChatProcessorService:
    """
    Service class responsible for processing Google chat messages.

    This class handles:
    - Pulling messages from Pub/Sub via the provided factory.
    - Processing and transforming Google chat messages using the provided utility.
    - Logging relevant events and errors during message processing.

    Attributes:
        logger: A logging instance.
        pubsub_puller_factory: A PubSubPullerFactory instance.
        google_chat_message_util: A GoogleChatMessageUtil instance.
        google_service: A GoogleService instance.
    """

    def __init__(
        self, logger, pubsub_puller_factory, google_chat_messages_utils, google_service
    ):
        """Initialize the GoogleChatProcessorService."""
        self.logger = logger
        self.pubsub_puller_factory = pubsub_puller_factory
        self.google_chat_messages_utils = google_chat_messages_utils
        self.google_service = google_service

    def pull_messages(self, project_id, subscription_id):
        """
        Listens to the given Pub/Sub subscription and processes incoming events.

        For each event:
        - If the event type is "google.workspace.events.subscription.v1.expirationReminder",
            renews the subscription using google_service.renew_subscription.
        - Otherwise, uses get_ldap_by_id(senderId) to obtain the sender's LDAP,
            then stores the event in Redis.

        Args:
            project_id (str): The Google Cloud project ID associated with the subscription.
            subscription_id (str): The Pub/Sub subscription ID to listen on.

        Returns:
            None: This function runs continuously and does not return until interrupted.

        Raises:
            ValueError: If any required field (e.g., senderId, spaceName, message) is missing from the payload.
            googleapiclient.errors.HttpError: If an error occurs during the subscription renewal process
        """

        self.logger.info(
            "Starting pull_messages with project_id: '%s' and subscription_id: '%s'",
            project_id,
            subscription_id,
        )

        if not subscription_id or not project_id:
            missing = []
            if not subscription_id:
                missing.append("subscription_id")
            if not project_id:
                missing.append("project_id")
            if missing:
                raise ValueError(
                    f"Missing required field(s) for pull_messages: {', '.join(missing)}"
                )

        puller = self.pubsub_puller_factory.get_puller_instance(
            project_id, subscription_id
        )
        puller.start_pulling_messages(self.callback)

    def callback(self, message):
        self.logger.debug("Received message: %s", message)
        attributes = message.attributes
        message_type_full = attributes.get("ce-type")

        try:
            data = json.loads(message.data.decode("utf-8"))
            self.logger.debug("Decoded message data: %s", data)
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            self.logger.error("Failed to decode/parse message data: %s", err)
            message.nack()
            return

        subscription_info = data.get("subscription")
        if EXPIRATION_REMINDER_EVENT == message_type_full:
            subscription_name = subscription_info.get("name")
            if not subscription_name:
                self.logger.error(
                    "No subscription_name provided in payload for expiration reminder event."
                )
                message.nack()
                raise ValueError(
                    "No subscription_name provided in payload for expiration reminder event."
                )

            self.logger.info("Renewing subscription: %s", subscription_name)

            self.google_service.renew_subscription(subscription_name)
            message.ack()
            self.logger.info("Subscription renewed and message acknowledged.")
            return

        if message_type_full in EVENT_TYPES:
            message_type = message_type_full.split(".")[-1] if message_type_full else ""

            chat_message = data.get("message")

            sender_name = chat_message.get("sender", {}).get("name", "")
            sender_id = sender_name.split("/")[1] if sender_name else ""

            sender_ldap = (
                self.google_service.get_ldap_by_id(sender_id) if sender_id else ""
            )

            self.google_chat_messages_utils.store_messages(
                sender_ldap, chat_message, message_type
            )

            message.ack()
            self.logger.info("Message processed and acknowledged.")
