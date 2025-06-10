from src.consumers.pubsub_puller import PubSubPuller, PullStatusResponse


def check_pulling_status(project_id: str, subscription_id: str) -> PullStatusResponse:
    """
    Check the message pulling status for a given Pub/Sub subscription.

    Args:
        project_id: Google Cloud project ID (must be non-empty)
        subscription_id: Pub/Sub subscription ID (must be non-empty)

    Returns:
        PullStatusResponse: An object containing the subscription's pull status with:
            - subscription_id: The ID of the subscription being checked
            - task_status: Current pull status code (RUNNING, NOT_STARTED, etc.)
            - message: Human-readable status description
            - timestamp: Last status update time (or None if not available)
    Raises:
        ValueError: If either project_id or subscription_id is None or empty
        RuntimeError: If there's a state inconsistency between local and Redis status
        Exception: Any errors from the underlying PubSubPuller or Redis operations
    """
    if not project_id:
        raise ValueError("project_id must be a non-empty string")
    if not subscription_id:
        raise ValueError("subscription_id must be a non-empty string")

    response_data = PubSubPuller(
        project_id, subscription_id
    ).check_pulling_messages_status()

    return response_data
