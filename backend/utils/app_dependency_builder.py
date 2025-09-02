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
from backend.consumers.consumer_controller import ConsumerController
from backend.utils.microsoft_chat_message_util import MicrosoftChatMessageUtil
from backend.utils.date_time_util import DateTimeUtil
from backend.consumers.microsoft_message_processor_service import (
    MicrosoftMessageProcessorService,
)
from backend.consumers.pubsub_puller_factory import PubSubPullerFactory
from backend.consumers.pubsub_puller import PubSubPuller
from backend.historical_data.historical_controller import HistoricalController
from backend.historical_data.microsoft_member_sync_service import (
    MicrosoftMemberSyncService,
)
from backend.frontend_service.ldap_service import LdapService
from backend.frontend_service.frontend_controller import FrontendController
from backend.frontend_service.microsoft_chat_analytics_service import (
    MicrosoftChatAnalyticsService,
)
from backend.frontend_service.microsoft_meeting_chat_topic_cache_service import (
    MicrosoftMeetingChatTopicCacheService,
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
    - HTTP API controllers (e.g. HistoryController, FrontendController, ConsumerController)

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
        self.date_time_util = DateTimeUtil(logger=self.logger)
        self.microsoft_chat_message_util = MicrosoftChatMessageUtil(
            logger=self.logger,
            redis_client=self.redis_client,
            microsoft_service=self.microsoft_service,
            date_time_util=self.date_time_util,
            retry_utils=self.retry_utils,
        )
        self.pubsub_puller_factory = PubSubPullerFactory(
            puller_creator=PubSubPuller, logger=self.logger
        )
        self.microsoft_message_processor_service = MicrosoftMessageProcessorService(
            logger=self.logger,
            pubsub_puller_factory=self.pubsub_puller_factory,
            microsoft_chat_message_util=self.microsoft_chat_message_util,
        )
        self.consumer_controller = ConsumerController(
            microsoft_message_processor_service=self.microsoft_message_processor_service
        )

        self.microsoft_member_sync_service = MicrosoftMemberSyncService(
            logger=self.logger,
            redis_client=self.redis_client,
            microsoft_service=self.microsoft_service,
            retry_utils=self.retry_utils,
        )
        self.historical_controller = HistoricalController(
            microsoft_member_sync_service=self.microsoft_member_sync_service
        )
        self.ldap_service = LdapService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
        )
        self.microsoft_chat_analytics_service = MicrosoftChatAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            date_time_util=self.date_time_util,
            ldap_service=self.ldap_service,
            retry_utils=self.retry_utils,
        )
        self.microsoft_meeting_chat_topic_cache_service = (
            MicrosoftMeetingChatTopicCacheService(
                logger=self.logger,
                redis_client=self.redis_client,
                microsoft_service=self.microsoft_service,
                retry_utils=self.retry_utils,
            )
        )

        self.frontend_controller = FrontendController(
            ldap_service=self.ldap_service,
            microsoft_chat_analytics_service=self.microsoft_chat_analytics_service,
            microsoft_meeting_chat_topic_cache_service=self.microsoft_meeting_chat_topic_cache_service,
        )
