import os
import json
import logging
import functions_framework
from google.cloud.pubsub_v1 import PublisherClient
from http import HTTPStatus


class _StructuredFormatter(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)
        return json.dumps({"severity": record.levelname, "message": message})


_handler = logging.StreamHandler()
_handler.setFormatter(_StructuredFormatter())
logging.root.setLevel(logging.INFO)
logging.root.handlers = [_handler]
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
        logger.error("Invalid JSON payload: %s", e)
        return "Invalid JSON", HTTPStatus.BAD_REQUEST

    if not payload:
        logger.error("Empty payload.")
        return "Empty payload", HTTPStatus.BAD_REQUEST

    if not publisher_client:
        logger.debug("Initializing Pub/Sub publisher client.")
        try:
            publisher_client = PublisherClient()
        except Exception as e:
            logger.critical("Failed to initialize Pub/Sub client: %s", e)
            return "Internal Server Error", HTTPStatus.INTERNAL_SERVER_ERROR

    topic_path = publisher_client.topic_path(PROJECT_ID, TOPIC_ID)
    logger.info("Pub/Sub topic path: %s", topic_path)

    try:
        message_data = json.dumps(payload).encode("utf-8")
        future = publisher_client.publish(topic_path, message_data)
        message_id = future.result(timeout=5)
        logger.info("Published Gerrit event to Pub/Sub. Message ID: %s", message_id)
        return "Gerrit Event published", HTTPStatus.OK
    except Exception as e:
        logger.error("Failed to publish Gerrit event: %s", e, exc_info=True)
        return "Gerrit: Failed to publish", HTTPStatus.INTERNAL_SERVER_ERROR
