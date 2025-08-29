class GoogleChatSubscriptionService:
    """
    Service for managing Google Workspace Events (Google Chat) subscriptions.
    """

    def __init__(self, logger, google_workspaceevents_client, retry_utils):
        """
        Initializes the GoogleChatSubscriptionService with necessary clients and logger.

        Args:
            logger: The logger instance for logging messages.
            google_client_factory: The GoogleClientFactory instance to build API clients.
        """
        if not logger:
            raise ValueError("Logger not provided.")
        if not google_workspaceevents_client:
            raise ValueError("GoogleWorkSpaceEventsClient not provided.")

        self.logger = logger
        self.google_workspaceevents_client = google_workspaceevents_client
        self.retry_utils = retry_utils

    def create_workspaces_subscriptions(
        self,
        project_id: str,
        topic_id: str,
        space_id: str,
        event_types: list[str],
    ) -> dict:
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

        body = {
            "target_resource": f"//chat.googleapis.com/spaces/{space_id}",
            "event_types": event_types,
            "notification_endpoint": {
                "pubsub_topic": f"projects/{project_id}/topics/{topic_id}"
            },
            "payload_options": {"include_resource": True},
        }

        subscription = self.google_workspaceevents_client.subscriptions().create(
            body=body
        )
        response = self.retry_utils.get_retry_on_transient.call(subscription.execute)

        self.logger.info(
            "Created subscription for space %s with event types %s on topic %s. Response: %s",
            space_id,
            event_types,
            topic_id,
            response,
        )
        return response
