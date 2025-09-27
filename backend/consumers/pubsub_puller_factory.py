from typing import Callable


class PubSubPullerFactory:
    """
    A factory class for creating and managing singleton instances of PubSubPuller.

    This class ensures that for a given project_id and subscription_id combination,
    only one instance of PubSubPuller is created and reused. This helps in
    managing resources and preventing redundant connections.
    """

    def __init__(
        self,
        puller_creator: Callable,
        logger,
        redis_client,
        asyncio_event_loop_manager,
        subscriber_client,
    ):
        """
        Initializes the PubSubPullerFactory with a callable object to create puller instances.

        Args:
            puller_creator (Callable[..., 'PubSubPuller']): A callable (like a class or function)
                that takes a variable number of arguments and returns a PubSubPuller instance.
                This allows the factory to create instances dynamically without being
                tied to a specific set of parameters.
            logger: Logger instance to output informational messages.
            redis_client: An initialized Redis client instance used by the PubSubPuller
                for caching or state management.
            asyncio_event_loop_manager: An instance of an AsyncioEventLoopManager
                responsible for managing the asyncio event loop for the puller.
            subscriber_client: An initialized Google Cloud Pub/Sub SubscriberClient
                instance used by the PubSubPuller to interact with the Pub/Sub service.
        """
        self.puller_creator = puller_creator
        self.logger = logger
        self.redis_client = redis_client
        self.subscriber_client = subscriber_client
        self.asyncio_event_loop_manager = asyncio_event_loop_manager

        self.pubsub_puller_instances = {}

    def get_puller_instance(self, project_id: str, subscription_id: str):
        """
        Retrieve a PubSubPuller instance for a specific project and subscription.

        If an instance for the given project_id and subscription_id already exists,
        this method returns the cached singleton instance. Otherwise, it creates a new
        one using the `puller_creator` callable, caches it, and then returns it.

        Args:
            project_id (str): The Google Cloud project ID.
            subscription_id (str): The Pub/Sub subscription ID.

        Returns:
            PubSubPuller: A singleton instance of PubSubPuller for the specified project and subscription.

        Example:
            puller_factory = PubSubPullerFactory(puller_creator=PubSubPuller, logger=logger_instance)
            puller1 = puller_factory.get_puller_instance(
                project_id="project-id-str",
                subscription_id="subscription-id-str",
            )
        """
        if not project_id or not subscription_id:
            raise ValueError(
                "project_id and subscription_id must be provided and not empty"
            )
        key = (project_id, subscription_id)
        if key not in self.pubsub_puller_instances:
            self.pubsub_puller_instances[key] = self.puller_creator(
                project_id=project_id,
                subscription_id=subscription_id,
                logger=self.logger,
                redis_client=self.redis_client,
                subscriber_client=self.subscriber_client,
                asyncio_event_loop_manager=self.asyncio_event_loop_manager,
            )
            self.logger.info(
                "Create new PubSubPuller instance: project_id: %s, subscription_id: %s",
                project_id,
                subscription_id,
            )

        return self.pubsub_puller_instances[key]
