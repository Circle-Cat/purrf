import os
import json
import asyncio
import logging
from enum import Enum
from redis import Redis
import functions_framework
from http import HTTPStatus
from msgraph import GraphServiceClient
from azure.identity import DefaultAzureCredential
from msgraph.generated.models.subscription import Subscription
from datetime import datetime, timezone, timedelta
from jsonschema import validate, ValidationError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MicrosoftLifecycleNotificationType(str, Enum):
    """Enum for Microsoft Graph lifecycle event types."""

    REAUTHORIZATION_REQUIRED = "reauthorizationRequired"
    SUBSCRIPTION_REMOVED = "subscriptionRemoved"
    MISSED = "missed"


REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_MAX_LIFETIME = 4320
MICROSOFT_SCOPES_LIST = ["https://graph.microsoft.com/.default"]
MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY = (
    "microsoft:client_state:{subscription_id}"
)
EVENT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "subscriptionId": {"type": "string"},
            "subscriptionExpirationDateTime": {"type": "string"},
            "tenantId": {"type": "string"},
            "clientState": {"type": "string"},
            "lifecycleEvent": {
                "type": "string",
                "enum": [e.value for e in MicrosoftLifecycleNotificationType],
            },
        },
        "required": [
            "subscriptionId",
            "subscriptionExpirationDateTime",
            "tenantId",
            "clientState",
            "lifecycleEvent",
        ],
    },
}


redis_client = None
graph_client = None


def _init_redis_client():
    """Initializes and returns a Redis client instance."""
    global redis_client
    if not redis_client:
        logger.debug("Initializing Redis client.")
        try:
            redis_client = Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                ssl=True,
                decode_responses=True,
            )

            redis_client.ping()
            logger.debug("Redis client initialized and connected successfully.")
        except Exception as e:
            logger.critical(
                f"Failed to initialize or connect to Redis client: {e}",
                exc_info=True,
            )
            raise


def _init_graph_client():
    """Initializes and returns a Microsoft GraphServiceClient instance."""
    global graph_client
    if not graph_client:
        try:
            graph_client = GraphServiceClient(
                DefaultAzureCredential(), MICROSOFT_SCOPES_LIST
            )
        except Exception as e:
            logger.critical(
                f"Failed to initialize or connect to Redis client: {e}",
                exc_info=True,
            )
            raise


def _validate_payload(payload_value: list) -> bool:
    """Validates the payload against the defined JSON schema."""
    try:
        validate(instance=payload_value, schema=EVENT_SCHEMA)
        return True
    except ValidationError as e:
        logger.error(f"Payload validation failed: {e.message}")
        return False


def _validate_identity(payload_value: list):
    """
    Validates the client state for each subscription in the payload.
    Ensures the provided clientState matches the one stored in Redis.
    """
    _init_redis_client()
    pipeline = redis_client.pipeline()
    provided = []
    for item in payload_value:
        subscription_id = item["subscriptionId"]
        provided_client_state = item["clientState"]
        provided.append(provided_client_state)

        redis_key = MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY.format(
            subscription_id=subscription_id
        )
        pipeline.get(redis_key)

    expected_client_state_list = pipeline.execute()

    for idx, provided_client_state in enumerate(provided):
        if provided_client_state != expected_client_state_list[idx]:
            logger.error(
                f"Client state mismatch for subscription {payload_value[idx]['subscriptionId']}"
            )
            return False
    return True


async def _renew_and_reauthorize_subscription(subscription_id: str):
    """Renews and reauthorizes a Microsoft Graph subscription."""
    _init_graph_client()
    current_time = datetime.now(timezone.utc)
    new_expiration = current_time + timedelta(
        minutes=MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_MAX_LIFETIME
    )

    updated_subscription = Subscription(expiration_date_time=new_expiration)

    try:
        result = await graph_client.subscriptions.by_subscription_id(
            subscription_id
        ).patch(updated_subscription)
        logger.info(f"Subscription {subscription_id} renewed successfully.")
        return result
    except Exception as e:
        logger.error(f"Failed to renew subscription {subscription_id}: {e}")
        raise


async def _process_lifecycle_event(notification_list):
    """Processes a list of lifecycle notifications."""
    for notification in notification_list:
        lifecycle_event = notification.get("lifecycleEvent")
        subscription_id = notification.get("subscriptionId")

        if lifecycle_event == MicrosoftLifecycleNotificationType.SUBSCRIPTION_REMOVED:
            logger.warning(f"Subscription {subscription_id} was removed.")

        elif lifecycle_event == MicrosoftLifecycleNotificationType.MISSED:
            logger.warning(f"Missed notifications for subscription {subscription_id}.")

        elif (
            lifecycle_event
            == MicrosoftLifecycleNotificationType.REAUTHORIZATION_REQUIRED
        ):
            await _renew_and_reauthorize_subscription(subscription_id)
        else:
            logger.warning(f"Unknown lifecycle event: {lifecycle_event}")

    return True


async def _handle_lifecycle_notification_webhook(request):
    """
    Cloud Function entry point to handle Microsoft Graph lifecycle notifications.
    Handles subscription validation and processes lifecycle events.
    """
    try:
        validation_token = request.args.get("validationToken")
        if validation_token:
            logger.info(
                "Validation token received from Microsoft notification webhook setup. Responding with token for validation handshake."
            )
            return validation_token, HTTPStatus.OK

        request_body = request.get_json(silent=True)
        if not request_body:
            logger.error(
                "Bad Request: Expected JSON body, but received empty or invalid JSON."
            )
            return "", HTTPStatus.BAD_REQUEST

        events = request_body.get("value", [])
        if not isinstance(events, list) or not events:
            logger.error(
                f"Bad Request: No events found in payload 'value' array. Received body: {request_body}"
            )
            return "", HTTPStatus.BAD_REQUEST

        is_validated_format = _validate_payload(events)
        if not is_validated_format:
            return "", HTTPStatus.BAD_REQUEST

        is_validate_identity = _validate_identity(events)
        if not is_validate_identity:
            logger.error("Access denied due to invalid client state.")
            return "", HTTPStatus.FORBIDDEN

        is_processed = await _process_lifecycle_event(events)
        if not is_processed:
            return "", HTTPStatus.INTERNAL_SERVER_ERROR
        return "", HTTPStatus.OK

    except Exception as e:
        logger.error(
            f"Unhandled Internal Server Error in notification_webhook: {e}",
            exc_info=True,
        )
        return "", HTTPStatus.INTERNAL_SERVER_ERROR


def lifecycle_notification_webhook_sync_wrapper(request):
    """
    Synchronous wrapper for the asynchronous webhook handler.
    Uses asyncio to run the async function.
    """
    try:
        # Try to get the current event loop. If none exists, create one.
        try:
            loop = asyncio.get_running_loop()
            logger.debug("Found existing running event loop.")
        except RuntimeError:
            logger.debug("No running event loop found, creating a new one.")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run the async function until it completes.
        result = loop.run_until_complete(
            _handle_lifecycle_notification_webhook(request)
        )
        return result
    except Exception as e:
        logger.error(
            f"Unhandled Internal Server Error in sync wrapper: {e}",
            exc_info=True,
        )
        return "", HTTPStatus.INTERNAL_SERVER_ERROR


@functions_framework.http
def lifecycle_notification_webhook(request):
    """
    Cloud Function entry point exposed to functions_framework.
    This acts as a synchronous interface, calling the async handler.
    """
    return lifecycle_notification_webhook_sync_wrapper(request)
