import os
import json
import logging
import functions_framework
from google.cloud.pubsub_v1 import PublisherClient
from http import HTTPStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID")
TOPIC_ID = os.environ.get("TOPIC_ID")

redis_client = None
publisher_client = None


@functions_framework.http
def gerrit_event_webhook(request):
    """
    Cloud Function to receive Gerrit webhook events and publish them to Pub/Sub.

    Steps:
    - Parses incoming JSON body.
    - Publishes the entire JSON payload to Pub/Sub.
    """
    global publisher_client

    try:
        payload = request.get_json(force=True)
    except Exception as e:
        logger.error(f"Invalid JSON payload: {e}")
        return "Invalid JSON", HTTPStatus.BAD_REQUEST

    if not payload:
        logger.error("Empty payload.")
        return "Empty payload", HTTPStatus.BAD_REQUEST

    if not publisher_client:
        logger.debug("Initializing Pub/Sub publisher client.")
        try:
            publisher_client = PublisherClient()
        except Exception as e:
            logger.critical(f"Failed to initialize Pub/Sub client: {e}")
            return "Internal Server Error", HTTPStatus.INTERNAL_SERVER_ERROR

    topic_path = publisher_client.topic_path(PROJECT_ID, TOPIC_ID)
    logger.info(f"Pub/Sub topic path: {topic_path}")

    try:
        message_data = json.dumps(payload).encode("utf-8")
        future = publisher_client.publish(topic_path, message_data)
        message_id = future.result(timeout=5)
        logger.info(f"Published Gerrit event to Pub/Sub. Message ID: {message_id}")
        return "Gerrit Event published", HTTPStatus.OK
    except Exception as e:
        logger.error(f"Failed to publish Gerrit event: {e}", exc_info=True)
        return "Gerrit: Failed to publish", HTTPStatus.INTERNAL_SERVER_ERROR
