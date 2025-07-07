from src.common.google_client import GoogleClientFactory
from tenacity import retry, stop_after_attempt, wait_exponential
from src.common.logger import get_logger

logger = get_logger()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
)
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
    logger.info(
        f"Creating subscription for space {space_id} with event types {event_types} on topic {topic_id}. Response: {response}"
    )
    return response
