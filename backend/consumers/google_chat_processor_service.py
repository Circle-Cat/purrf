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
    - Processing and transforming Google chat messages using the provided utility.
    - Logging relevant events and errors during message processing.

    Attributes:
        logger: A logging instance.
        google_chat_message_util: A GoogleChatMessageUtil instance.
        google_service: A GoogleService instance.
    """

    def __init__(self, logger, google_chat_messages_utils, google_service):
        """Initialize the GoogleChatProcessorService."""
        self.logger = logger
        self.google_chat_messages_utils = google_chat_messages_utils
        self.google_service = google_service

    def process_event(self, data: dict, attributes: dict):
        """
        Process a single Google Chat event (pure business logic, no ack/nack).

        Args:
            data: Decoded JSON payload from the Pub/Sub message.
            attributes: Message attributes dict (contains CloudEvent metadata like `ce-type`).

        Raises:
            ValueError: If the event type is unsupported or required fields are missing.
        """
        message_type_full = attributes.get("ce-type")

        subscription_info = data.get("subscription")
        if EXPIRATION_REMINDER_EVENT == message_type_full:
            subscription_name = subscription_info.get("name")
            if not subscription_name:
                raise ValueError(
                    "No subscription_name provided in payload for expiration reminder event."
                )
            self.logger.info(
                "[GoogleChatProcessorService] Renewing subscription: %s",
                subscription_name,
            )
            self.google_service.renew_subscription(subscription_name)
            self.logger.info("[GoogleChatProcessorService] Subscription renewed.")
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
            self.logger.info(
                "[GoogleChatProcessorService] Google Chat message processed."
            )
        else:
            raise ValueError(f"Unsupported Google Chat event: {message_type_full}")
