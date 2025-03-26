# Implement those function in this file:
# create_pubsub_topic(publisher_client, project_id, topic_id)
# create_workspaces_subscriptions(project_id, topic_id, client, space_id, event_types)
# subscribe_chat(topic_id, subscription_id, space_id)


from tools.log.logger import setup_logger
from google.authentication_utils import GoogleClientFactory
from google.cloud.pubsub_v1.types import Subscription
import logging

setup_logger()


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
        request={"name": subscription_path, "topic": topic_path, "expiration_policy": {}}
    )

    logging.info(f"Subscription created: {subscription_path}")
    return subscription_path
