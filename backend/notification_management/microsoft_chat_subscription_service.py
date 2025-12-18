import secrets
from datetime import datetime, timedelta, timezone
from backend.common.constants import (
    MicrosoftChatMessagesChangeType,
    MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_MAX_LIFETIME,
    MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE,
    MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY,
    MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_CLIENT_STATE_BYTE_LENGTH,
)


class MicrosoftChatSubscriptionService:
    """
    Service class to manage Microsoft Teams chat message subscriptions,
    including subscription creation, renewal, and client_state management in Redis.
    """

    def __init__(self, logger, redis_client, microsoft_service):
        """
        Initializes the MicrosoftChatSubscriptionService with necessary clients and logger.
        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            microsoft_service: The MicrosoftService instance.
        """
        if not logger:
            raise ValueError("Logger client not created.")
        if not redis_client:
            raise ValueError("Redis client not created.")
        if not microsoft_service:
            raise ValueError("MicrosoftService not created.")
        self.logger = logger
        self.redis_client = redis_client
        self.microsoft_service = microsoft_service

    def _generate_client_state(self):
        """
        Generates a secure, random client_state value used to verify Microsoft subscription notifications.
        Returns:
            str: A secure random string suitable for use as client_state.
        """
        client_state = secrets.token_urlsafe(
            MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_CLIENT_STATE_BYTE_LENGTH
        )
        return client_state

    def _update_client_state(
        self,
        subscription_id: str,
        client_state: str,
        legacy_subscription_id: str | None,
    ):
        """
        Stores the generated client_state in Redis for lifecycle event validation. Optionally deletes a legacy entry.
        Args:
            subscription_id (str): The new Microsoft Graph subscription ID.
            client_state (str): The client_state to store.
            legacy_subscription_id (str | None): Optional. If provided, deletes the previous client_state entry.
        Raises:
            ValueError: If required parameters are missing or Redis client creation fails.
            RuntimeError: If Redis pipeline execution fails.
        """
        if not subscription_id:
            raise ValueError("Missing required parameter: subscription_id.")
        if not client_state:
            raise ValueError("Missing required parameter: client_state.")
        pipeline = self.redis_client.pipeline()
        pipeline.set(
            MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY.format(
                subscription_id=subscription_id
            ),
            client_state,
        )
        if legacy_subscription_id:
            pipeline.delete(
                MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY.format(
                    subscription_id=legacy_subscription_id
                )
            )
        try:
            pipeline.execute()
            self.logger.info(
                "Successfully updated client_state for subscription_id: %s",
                subscription_id,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to update the client_state in Redis. New ID: '{subscription_id}', Legacy ID: '{legacy_subscription_id}'."
            ) from e

    async def subscribe_chat_messages(
        self, chat_id: str, notification_url: str, lifecycle_notification_url: str
    ) -> tuple[str, dict]:
        """
        Subscribes to Microsoft Teams chat message notifications, reuses valid subscriptions if possible,
        or deletes outdated ones and creates a new subscription if needed.
        This function checks for an existing Microsoft Graph API subscription for the given chat ID.
        If a valid subscription exists (resource, change_type, notification URLs match and not expired),
        it reuses it. Otherwise, outdated subscriptions targeting the same chat are deleted, and a new
        subscription is created with a 3-day expiration period (4320 minutes).
        Finally, the secure, random client_state is stored in Redis to enable validation of incoming notifications.
        Args:
            chat_id: The unique identifier of the Teams chat to subscribe to.
            notification_url: The endpoint URL where chat message notifications will be delivered.
            lifecycle_notification_url: The endpoint URL for lifecycle notifications (e.g., subscription expiration).
        Returns:
            tuple[str, dict]: A tuple containing:
                - A status message string indicating the result ("Subscription created successfully for chat_id ...").
                - A dictionary with subscription metadata:
                    {
                        "expiration_timestamp": ISO timestamp string,
                        "chat_id": original chat_id,
                        "subscription_id": created or reused subscription ID
                    }
        Raises:
            ValueError: If any required parameter (`chat_id`, `notification_url`, `lifecycle_notification_url`) is missing or empty.
            ValueError: If the Microsoft Graph API client could not be created.
        Example:
            message, info = await subscribe_chat_messages(
                "19:meeting_ID@thread.skype",
                "https://example.com/notifications",
                "https://example.com/lifecycle"
            )
            # message: "Subscription created successfully for chat_id 19:meeting_ID@thread.skype."
            # info: {
            #     "expiration_timestamp": "2025-05-27T12:34:56.000Z",
            #     "chat_id": "19:meeting_ID@thread.skype",
            #     "subscription_id": "abc123..."
            # }
        """
        missing_params = []
        if not chat_id:
            missing_params.append("chat_id")
        if not notification_url:
            missing_params.append("notification_url")
        if not lifecycle_notification_url:
            missing_params.append("lifecycle_notification_url")
        if missing_params:
            raise ValueError(
                f"The following required parameters are missing or empty: {', '.join(missing_params)}"
            )
        current_time = datetime.now(timezone.utc)
        expiration = current_time + timedelta(
            minutes=MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_MAX_LIFETIME
        )
        expiration_date_time = ""
        sub_id = ""
        self.logger.info(
            "Attempting to subscribe to chat messages for chat_id: %s", chat_id
        )
        subscription_resource = (
            MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE.format(chat_id=chat_id)
        )
        change_types = [e.value for e in MicrosoftChatMessagesChangeType]
        change_type_str = ",".join(change_types)
        legacy_subscription_id = None
        subscriptions = await self.microsoft_service.list_all_subscriptions()
        for sub in subscriptions:
            if sub.resource != subscription_resource:
                continue
            if (
                sub.expiration_date_time > current_time
                and sub.change_type == change_type_str
                and sub.notification_url == notification_url
                and sub.lifecycle_notification_url == lifecycle_notification_url
            ):
                self.logger.info(
                    "Found valid existing subscription. No need to create a new one. chat ID: %s, subscription ID: %s",
                    chat_id,
                    sub.id,
                )
                self.logger.debug("Subscription details: %s", sub)
                expiration_date_time = sub.expiration_date_time
                sub_id = sub.id
                break
            await self.microsoft_service.delete_subscription(sub.id)
            legacy_subscription_id = sub.id
            self.logger.info("Deleted outdated subscription: %s", sub.id)
        if not sub_id:
            client_state = self._generate_client_state()
            result = await self.microsoft_service.create_subscription(
                change_type=change_type_str,
                notification_url=notification_url,
                lifecycle_notification_url=lifecycle_notification_url,
                resource=subscription_resource,
                expiration_date_time=expiration.isoformat(),
                client_state=client_state,
            )
            self.logger.info("Created new subscription: %s", result.id)
            self.logger.debug("New subscription details: %s", result)
            expiration_date_time = result.expiration_date_time
            sub_id = result.id
            self._update_client_state(sub_id, client_state, legacy_subscription_id)
        return f"Subscription created successfully for chat_id {chat_id}.", {
            "expiration_timestamp": expiration_date_time,
            "chat_id": chat_id,
            "subscription_id": sub_id,
        }
