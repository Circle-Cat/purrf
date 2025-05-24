from msgraph.generated.models.subscription import Subscription
from src.common.microsoft_client import MicrosoftClientFactory
from src.common.logger import get_logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from datetime import datetime, timedelta, timezone
from src.common.constants import (
    MicrosoftChatMessagesChangeType,
    MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_MAX_LIFETIME,
    MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE,
)

logger = get_logger()


async def subscribe_chat_messages(
    chat_id: str, notification_url: str, lifecycle_notification_url: str
) -> tuple[str, dict]:
    """
    Subscribes to Microsoft Teams chat message notifications, reuses valid subscriptions if possible,
    or deletes outdated ones and creates a new subscription if needed.

    This function checks for an existing Microsoft Graph API subscription for the given chat ID.
    If a valid subscription exists (resource, change_type, notification URLs match and not expired),
    it reuses it. Otherwise, outdated subscriptions targeting the same chat are deleted, and a new
    subscription is created with a 3-day expiration period (4320 minutes).

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
    logger.info("Attempting to subscribe to chat messages for chat_id: %s", chat_id)

    client = MicrosoftClientFactory().create_graph_service_client()
    if not client:
        raise ValueError("Failed to create Microsoft Graph API client.")

    subscription_resource = MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE.format(
        chat_id=chat_id
    )
    change_types = [e.value for e in MicrosoftChatMessagesChangeType]
    change_type_str = ",".join(change_types)

    subscriptions = await client.subscriptions.get()
    for sub in subscriptions.value:
        if sub.resource != subscription_resource:
            continue

        if (
            sub.expiration_date_time > current_time
            and sub.change_type == change_type_str
            and sub.notification_url == notification_url
            and sub.lifecycle_notification_url == lifecycle_notification_url
        ):
            logger.info(
                "Found valid existing subscription. No need to create a new one.",
                chat_id,
                sub.id,
            )
            logger.debug("Subscription details: %s", sub)
            expiration_date_time = sub.expiration_date_time
            sub_id = sub.id
            break

        await client.subscriptions.by_subscription_id(sub.id).delete()
        logger.info("Deleted outdated subscription: %s", sub.id)

    if not sub_id:
        request_body = Subscription(
            change_type=change_type_str,
            notification_url=notification_url,
            lifecycle_notification_url=lifecycle_notification_url,
            resource=subscription_resource,
            expiration_date_time=expiration.isoformat(),
            client_state="secretClientValue",
        )
        result = await client.subscriptions.post(request_body)
        logger.info("Created new subscription: %s", result.id)
        logger.debug("New subscription details: %s", result)

        expiration_date_time = result.expiration_date_time
        sub_id = result.id

    return f"Subscription created successfully for chat_id {chat_id}.", {
        "expiration_timestamp": expiration_date_time,
        "chat_id": chat_id,
        "subscription_id": sub_id,
    }
