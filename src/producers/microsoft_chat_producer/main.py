import os
import json

import functions_framework
from google.cloud.pubsub_v1 import PublisherClient
from concurrent.futures import TimeoutError
from http import HTTPStatus
import logging
from redis import Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


PROJECT_ID = os.environ.get("PROJECT_ID")
TOPIC_ID = os.environ.get("TOPIC_ID")
REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
EXPECTED_CLIENT_STATE_KEY_FORMAT = "microsoft:client_state:{microsoft_subscription_id}"

redis_client = None
publisher_client = None


def _validate_payload(payload: dict) -> bool:
    """Validate the Microsoft Graph notification payload.

    Args:
        payload (dict): Parsed JSON payload from request.

    Returns:
        is_valid: bool
    """
    if not isinstance(payload, dict):
        logger.error("Payload must be a JSON object.")
        return False

    required_fields = ["subscriptionId", "clientState", "resourceData"]
    for field in required_fields:
        if field not in payload:
            logger.error(f"Missing required field: {field}")
            return False

        if not payload.get(field):
            logger.error(f"Field '{field}' must not be empty or None.")
            return False
    return True


@functions_framework.http
def notification_webhook(request):
    """
    Handles incoming Microsoft Graph change notifications and publishes them
    to Google Cloud Pub/Sub after validation.

    This function serves as an HTTP webhook endpoint for Microsoft Graph subscriptions.
    It performs several key steps:

    1.  **Validation Handshake:** Responds to Microsoft's initial webhook setup
        requests by echoing the `validationToken` found in the query parameters.
    2.  **Request Body Validation:** Ensures the incoming request is a valid JSON
        payload containing a list of notification events in the `value` field.
    3.  **Security Validation (Client State):** For each event, it retrieves an
        `expected_client_state` from Redis using the `subscriptionId` found in the
        notification. It then compares this expected state with the `clientState`
        provided in the notification payload. This mechanism is crucial for
        verifying the authenticity and integrity of the notification.
    4.  **Pub/Sub Publishing:** Validated events are serialized as JSON and
        published asynchronously to a configured Google Cloud Pub/Sub topic.

    Global Redis and Pub/Sub publisher clients are initialized on first use to
    optimize performance.

    Args:
        request (flask.Request): The incoming HTTP request object from
                                 functions_framework. It's expected to contain
                                 either:
                                 - A `validationToken` as a query parameter for
                                   webhook setup.
                                 - A JSON body with a `value` key containing a
                                   list of Microsoft Graph change notification events.

    Returns:
        tuple[str, int]: A tuple containing:
                         - An empty string `""` or the `validationToken` itself.
                         - An HTTP status code indicating the outcome of the request:
                           - `HTTPStatus.OK` (200): For successful webhook validation handshake.
                           - `HTTPStatus.ACCEPTED` (202): For successful processing
                             and publishing of notification events.
                           - `HTTPStatus.BAD_REQUEST` (400): If the request format
                             is incorrect (e.g., missing JSON body, invalid `value`
                             array, or failed event payload validation).
                           - `HTTPStatus.FORBIDDEN` (403): If the `clientState` in
                             the notification does not match the expected state
                             retrieved from Redis, indicating a potential security
                             breach or misconfiguration.
                           - `HTTPStatus.INTERNAL_SERVER_ERROR` (500): For issues
                             related to Redis connectivity/initialization, Pub/Sub
                             client initialization, or Pub/Sub message publishing
                             failures/timeouts, or any other unhandled server error.

    Side Effects:
        - Initializes global `redis_client` and `publisher_client` if they are `None`.
        - Interacts with a Redis instance to retrieve expected client states.
        - Publishes messages to a Google Cloud Pub/Sub topic.
        - Logs various informational, error, and critical messages using the `logger`.
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

        futures = []
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
                if not redis_client:
                    logger.critical("Failed to initialize Redis client.")
                    return "", HTTPStatus.INTERNAL_SERVER_ERROR

                redis_client.ping()
                logger.debug("Redis client initialized and connected successfully.")
            except Exception as e:
                logger.critical(
                    f"Failed to initialize or connect to Redis client: {e}",
                    exc_info=True,
                )
                return "", HTTPStatus.INTERNAL_SERVER_ERROR

        pipeline = redis_client.pipeline()

        for event in events:
            is_validated = _validate_payload(event)
            if not is_validated:
                logger.error(f"Event payload validation failed.")
                return "", HTTPStatus.BAD_REQUEST

            microsoft_subscription_id = event.get(
                "subscriptionId", "unknown_subscription"
            )
            redis_key = EXPECTED_CLIENT_STATE_KEY_FORMAT.format(
                microsoft_subscription_id=microsoft_subscription_id
            )
            pipeline.get(redis_key)
            logger.debug(f"Queued Redis GET for key: {redis_key}")

        expected_client_state_list = pipeline.execute()
        logger.debug(
            f"Fetched {len(expected_client_state_list)} expected client states from Redis."
        )

        global publisher_client
        if not publisher_client:
            logger.debug("Initializing Pub/Sub publisher client.")
            publisher_client = PublisherClient()
            if not publisher_client:
                logger.critical("Failed to initialize Publisher client.")
                return "", HTTPStatus.INTERNAL_SERVER_ERROR

        topic_path = publisher_client.topic_path(PROJECT_ID, TOPIC_ID)
        logger.info(f"Pub/Sub topic path: {topic_path}")

        for i, (event, expected_client_state_from_redis) in enumerate(
            zip(events, expected_client_state_list)
        ):
            client_state = event.get("clientState")
            subscription_id = event.get("subscriptionId", "unknown_subscription")

            if not expected_client_state_from_redis:
                logger.error(
                    f"Forbidden: Expected client state not found in Redis for subscriptionId: {subscription_id}."
                )
                return "", HTTPStatus.FORBIDDEN

            if client_state != expected_client_state_from_redis:
                logger.error(
                    f"Forbidden: clientState mismatch for subscriptionId: {subscription_id}.Received: '{client_state}'"
                )
                return "", HTTPStatus.FORBIDDEN

            try:
                message_data = json.dumps(event).encode("utf-8")
                future = publisher_client.publish(topic_path, message_data)
                futures.append(future)
                logger.info(
                    f"Successfully queued Pub/Sub message for subscriptionId: {subscription_id}."
                )
            except Exception as e:
                logger.error(
                    f"Failed to queue Pub/Sub message for subscriptionId {subscription_id}: {e}",
                    exc_info=True,
                )
                return "", HTTPStatus.INTERNAL_SERVER_ERROR

        last_message_id = None
        for i, future in enumerate(futures):
            try:
                message_id = future.result(timeout=3)
                last_message_id = message_id
                logger.info(
                    f"Successfully published message {i + 1} to Pub/Sub. Message ID: {message_id}"
                )
            except TimeoutError:
                logger.error(
                    f"Publishing message {i + 1} timed out after 3 seconds for subscriptionId: {events[i].get('subscriptionId', 'N/A')}."
                )
                return "", HTTPStatus.INTERNAL_SERVER_ERROR
            except Exception as e:
                logger.error(
                    f"Error getting publish result for message {i + 1} (subscriptionId: {events[i].get('subscriptionId', 'N/A')}): {e}",
                    exc_info=True,
                )
                return "", HTTPStatus.INTERNAL_SERVER_ERROR

        logger.info(
            f"Successfully processed and published {len(events)} messages to {topic_path}. Last message ID: {last_message_id if last_message_id else 'N/A'}"
        )
        return "", HTTPStatus.ACCEPTED

    except Exception as e:
        logger.critical(
            f"Unhandled Internal Server Error in notification_webhook: {e}",
            exc_info=True,
        )
        return "", HTTPStatus.INTERNAL_SERVER_ERROR
