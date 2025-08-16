from backend.common.logger import get_logger
from backend.utils.retry_utils import RetryUtils
from backend.common.redis_client import RedisClientFactory
from backend.common.microsoft_graph_service_client import MicrosoftGraphServiceClient
from backend.service.microsoft_service import MicrosoftService
from backend.notification_management.microsoft_chat_subscription_service import (
    MicrosoftChatSubscriptionService,
)
from backend.notification_management.notification_controller import (
    NotificationController,
)


class AppDependencyBuilder:
    """
    A builder class responsible for constructing all service and controller dependencies
    used throughout the application.

    This class acts as a centralized place for wiring together core infrastructure such as:
    - Logging
    - Redis client
    - Microsoft Graph client
    - Business services (e.g. MicrosoftService, MicrosoftChatService)
    - HTTP API controllers (e.g. HistoryController, FrontendController, ConsumersController)

    Example:
        builder = AppDependencyBuilder()
        app = create_app(notification_controller = builder.notification_controller)
    """

    def __init__(self):
        self.logger = get_logger()
        self.retry_utils = RetryUtils()

        self.redis_client = RedisClientFactory().create_redis_client()
        self.graph_client = MicrosoftGraphServiceClient().get_graph_service_client

        self.microsoft_service = MicrosoftService(
            logger=self.logger,
            graph_service_client=self.graph_client,
            retry_utils=self.retry_utils,
        )
        self.microsoft_chat_subscription_service = MicrosoftChatSubscriptionService(
            logger=self.logger,
            redis_client=self.redis_client,
            microsoft_service=self.microsoft_service,
        )

        self.notification_controller = NotificationController(
            microsoft_chat_subscription_service=self.microsoft_chat_subscription_service
        )
