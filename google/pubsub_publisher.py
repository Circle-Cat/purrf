# Implement those function in this file:
# create_pubsub_topic(publisher_client, project_id, topic_id)
# create_workspaces_subscriptions(project_id, topic_id, client, space_id, event_types)
# subscribe_chat(topic_id, subscription_id, space_id)


from tools.log.logger import setup_logger
from google.authentication_utils import GoogleClientFactory
from tenacity import retry, stop_after_attempt, wait_exponential
from google.cloud.pubsub_v1.types import Subscription
import logging
from google.constants import EVENT_TYPES

setup_logger()


def create_pubsub_topic(project_id, topic_id):
    """
    Creates a Pub/Sub topic in the specified project.

    Args:
        publisher_client (google.cloud.pubsub_v1.PublisherClient): The Publisher client instance.
        project_id (str): The ID of your Google Cloud project.
        topic_id (str): The ID of the topic to create.

    Returns:
        google.cloud.pubsub_v1.types.Topic: The created Topic object.

    Raises:
        ValueError: If project_id or topic_id is empty.
    """
    if not project_id or not topic_id:
        raise ValueError("Project_id and topic_id must be provided.")

    publisher_client = GoogleClientFactory().create_publisher_client()
    topic_path = publisher_client.topic_path(project_id, topic_id)
    topic = publisher_client.create_topic(name=topic_path)
    logging.info(f"Topic created: {topic_path}")
    return topic


def create_workspaces_subscriptions(project_id, topic_id, space_id, event_types):
    """
    Creates a Google Workspace Events subscription for a specific space.

    Args:
        project_id (str): The ID of your Google Cloud project.
        topic_id (str): The Pub/Sub topic ID where events will be published.
        space_id (str): The ID of the Google Chat space to subscribe to.
        event_types (list): A list of event types to listen for.

    Returns:
        dict: The API response containing the subscription details.

    Raises:
        ValueError: If any of the required parameters are missing.
    """

    if not project_id or not topic_id or not space_id or not event_types:
        raise ValueError(
            "All parameters (project_id, topic_id, space_id, event_types) must be provided."
        )

    workspaceevents = GoogleClientFactory().create_workspaceevents_client()
    BODY = {
        "target_resource": f"//chat.googleapis.com/spaces/{space_id}",
        "event_types": event_types,
        "notification_endpoint": {
            "pubsub_topic": f"projects/{project_id}/topics/{topic_id}"
        },
        "payload_options": {"include_resource": True},
    }
    response = workspaceevents.subscriptions().create(body=BODY).execute()
    logging.info(
        f"Creating subscription for space {space_id} with event types {event_types} on topic {topic_id}. Response: {response}"
    )
    return response


def create_subscription(project_id, topic_id, subscription_id):
    """
    Creates a Google Cloud Pub/Sub subscription for a given topic with no expiration.

    Args:
        project_id (str): Google Cloud Project ID.
        topic_id (str): The Pub/Sub topic ID to subscribe to.
        subscription_id (str): The subscription ID to be created.

    Returns:
        str: The name of the created subscription.

    Raises:
        ValueError: if project_id or topic_id or subscription_id is empty.
    """

    if not project_id or not topic_id or not subscription_id:
        raise ValueError(
            "project_id and topic_id and subscription_id must be provided."
        )

    subscriber = GoogleClientFactory().create_subscriber_client()
    topic_path = subscriber.topic_path(project_id, topic_id)
    subscription_path = subscriber.subscription_path(project_id, subscription_id)

    subscriber.create_subscription(
        request={
            "name": subscription_path,
            "topic": topic_path,
            "expiration_policy": {},
        }
    )

    logging.info(f"Subscription created: {subscription_path}")
    return subscription_path


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
)
def subscribe_chat(project_id, topic_id, subscription_id, space_id, request_data=None):
    """Subscribes to events for a given Google Chat space.

    This function:
    1. Creates a Pub/Sub topic if it does not exist.
    2. Creates a subscription for the topic.
    3. Registers the space for workspace subscriptions.

    Args:
        project_id (str): Google Cloud Project ID.
        topic_id (str): Pub/Sub topic ID.
        subscription_id (str): Pub/Sub subscription ID.
        space_id (str): Google Chat space ID.

    Returns:
        - A dictionary containing the response from the Google Workspace API for the subscription request.
        - The created Pub/Sub subscription object.
    """
    if not project_id or not topic_id or not subscription_id or not space_id:
        missing_params = []
        if not project_id:
            missing_params.append("project_id")
        if not topic_id:
            missing_params.append("topic_id")
        if not subscription_id:
            missing_params.append("subscription_id")
        if not space_id:
            missing_params.append("space_id")
        missing = ", ".join(missing_params)
        logging.error(
            "Missing required parameters: {missing}. Request data: {request_data}"
        )
        raise ValueError(
            "Missing required parameters: {missing}. Request data: {request_data}"
        )
    try:
        pubsub_topic = create_pubsub_topic(project_id, topic_id)
    except Exception as e:
        logging.error(f"Failed to create Pub/Sub topic '{topic_id}': {e}")
        raise
    try:
        pubsub_subscription = create_subscription(project_id, topic_id, subscription_id)
    except Exception as e:
        logging.error(f"Failed to create Pub/Sub subscription '{subscription_id}': {e}")
        raise
    try:
        response = create_workspaces_subscriptions(
            project_id, topic_id, space_id, EVENT_TYPES
        )
    except Exception as e:
        logging.error(
            f"Failed to create Pub/Sub workspace subscription '{space_id}': {e}"
        )
        raise

    success = (
        response.get("done") is True
        and response.get("response", {}).get("state") == "ACTIVE"
    )
    if success:
        logging.info(
            f"Subscription successful | project_id: {project_id} | space_id: {space_id} | topic: {topic_id} | subscription: {subscription_id}"
        )
    else:
        logging.warning(
            f"Subscription failed | project_id: {project_id} | space_id: {space_id} | topic: {topic_id} | subscription: {subscription_id}"
        )
    return success, response
