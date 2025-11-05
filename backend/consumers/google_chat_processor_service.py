import json
from backend.common.constants import (
    EXPIRATION_REMINDER_EVENT,
    ALL_GOOGLE_CHAT_EVENT_TYPES,
    SINGLE_GOOGLE_CHAT_EVENT_TYPES,
    GoogleChatEventType,
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

        This method initializes a Pub/Sub puller for the given `project_id` and `subscription_id`,
        and registers the instance's `callback` method as the message handler.

        The message handler (`callback`) will:
          - Renew expiring Workspace subscription events
          - Process Google Chat events and store messages in Redis

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
        """
        Handles individual Pub/Sub messages pulled from a Workspace Chat subscription.

        Depending on the CloudEvent type (`ce-type` attribute), the handler performs one of:
          - **Subscription Expiration Reminder**:
                Calls `google_service.renew_subscription()` to renew the expiring subscription.
          - **Google Chat Events**:
                Parses the event payload, resolves sender LDAP(s), and stores the messages
                into Redis via `google_chat_messages_utils.store_messages()`.

        Unsupported event types are negatively acknowledged (nack).

        Args:
            message (google.cloud.pubsub_v1.subscriber.message.Message):
                The Pub/Sub message object containing:
                - `attributes`: includes CloudEvent metadata (e.g. `ce-type`).
                - `data`: JSON-encoded Workspace or Chat event payload.

        Raises:
            ValueError: If required fields (e.g., subscription name, message content) are missing
                        or malformed within the event payload.

        Side Effects:
            - Calls external Google API to renew subscriptions.
            - Persists parsed messages into Redis.
            - Acknowledges or nacks Pub/Sub messages depending on processing result.

        Returns:
            None
        """
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

        if message_type_full in ALL_GOOGLE_CHAT_EVENT_TYPES:
            message_type = message_type_full.split(".")[-1] if message_type_full else ""
            message_enum = GoogleChatEventType(message_type)
            ldaps_dict = {}
            if message_type_full in SINGLE_GOOGLE_CHAT_EVENT_TYPES:
                chat_message = data.get("message")
                messages_list = [data]
                if GoogleChatEventType.CREATED == message_enum:
                    sender_name = chat_message.get("sender", {}).get("name", "")
                    sender_id = sender_name.split("/")[1] if sender_name else ""
                    sender_ldap = (
                        self.google_service.get_ldap_by_id(sender_id)
                        if sender_id
                        else ""
                    )
                    ldaps_dict = {sender_name: sender_ldap}
            else:
                messages_list = data.get("messages")
                if GoogleChatEventType.BATCH_CREATED == message_enum:
                    ldaps_dict = self.google_service.list_directory_all_people_ldap()

            self.google_chat_messages_utils.store_messages(
                ldaps_dict, messages_list, message_enum
            )
            message.ack()
            self.logger.info("Message processed and acknowledged.")
        else:
            message.nack()
            self.logger.info(
                "Received unsupporited Google Chat event: %s", message_type_full
            )
