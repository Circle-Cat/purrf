import os
from backend.common.logger import get_logger
from backend.utils.retry_utils import RetryUtils
from backend.common.redis_client import RedisClient
from backend.common.google_client import GoogleClient
from backend.common.jira_client import JiraClient
from backend.service.google_service import GoogleService
from backend.common.microsoft_graph_service_client import MicrosoftGraphServiceClient
from backend.common.json_schema_validator import JsonSchemaValidator
from backend.common.gerrit_client import GerritClient
from backend.service.microsoft_service import MicrosoftService
from backend.notification_management.microsoft_chat_subscription_service import (
    MicrosoftChatSubscriptionService,
)
from backend.notification_management.google_chat_subscription_service import (
    GoogleChatSubscriptionService,
)

from backend.notification_management.notification_controller import (
    NotificationController,
)
from backend.utils.google_chat_message_utils import GoogleChatMessagesUtils
from backend.consumers.consumer_controller import ConsumerController
from backend.utils.microsoft_chat_message_util import MicrosoftChatMessageUtil
from backend.utils.date_time_util import DateTimeUtil
from backend.consumers.microsoft_message_processor_service import (
    MicrosoftMessageProcessorService,
)
from backend.consumers.google_chat_processor_service import GoogleChatProcessorService
from backend.consumers.pubsub_puller_factory import PubSubPullerFactory
from backend.consumers.pubsub_puller import PubSubPuller
from backend.consumers.gerrit_processor_service import GerritProcessorService
from backend.consumers.pubsub_pull_manager import PubSubPullManager
from backend.historical_data.historical_controller import HistoricalController
from backend.historical_data.microsoft_member_sync_service import (
    MicrosoftMemberSyncService,
)
from backend.historical_data.google_calendar_sync_service import (
    GoogleCalendarSyncService,
)
from backend.historical_data.gerrit_sync_service import GerritSyncService
from backend.frontend_service.ldap_service import LdapService
from backend.frontend_service.jira_analytics_service import JiraAnalyticsService
from backend.frontend_service.google_calendar_analytics_service import (
    GoogleCalendarAnalyticsService,
)
from backend.frontend_service.frontend_controller import FrontendController
from backend.frontend_service.microsoft_chat_analytics_service import (
    MicrosoftChatAnalyticsService,
)
from backend.frontend_service.microsoft_meeting_chat_topic_cache_service import (
    MicrosoftMeetingChatTopicCacheService,
)
from backend.frontend_service.gerrit_analytics_service import GerritAnalyticsService
from backend.historical_data.microsoft_chat_history_sync_service import (
    MicrosoftChatHistorySyncService,
)
from backend.historical_data.jira_history_sync_service import JiraHistorySyncService
from backend.service.jira_search_service import JiraSearchService
from backend.frontend_service.google_chat_analytics_service import (
    GoogleChatAnalyticsService,
)
from backend.frontend_service.summary_service import SummaryService
from backend.common.environment_constants import (
    JIRA_SERVER,
    JIRA_USER,
)
from backend.historical_data.google_chat_history_sync_service import (
    GoogleChatHistorySyncService,
)
from backend.common.asyncio_event_loop_manager import AsyncioEventLoopManager
from backend.utils.fast_app_factory import FastAppFactory
from backend.authentication.authentication_controller import AuthenticationController
from backend.authentication.authentication_service import AuthenticationService
from backend.repository.users_repository import UsersRepository
from backend.repository.experience_repository import ExperienceRepository
from backend.repository.training_repository import TrainingRepository
from backend.profile.profile_query_service import ProfileQueryService
from backend.profile.profile_command_service import ProfileCommandService
from backend.profile.profile_mapper import ProfileMapper


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
        jira_server = os.getenv(JIRA_SERVER)
        jira_user = os.getenv(JIRA_USER)

        self.logger = get_logger()
        self.retry_utils = RetryUtils()

        self.gerrit_client = GerritClient()
        self.redis_client = RedisClient(
            logger=self.logger,
            retry_utils=self.retry_utils,
        ).get_redis_client()
        self.graph_client = MicrosoftGraphServiceClient().get_graph_service_client
        self.google_client = GoogleClient(
            logger=self.logger,
            retry_utils=self.retry_utils,
        )
        self.json_schema_validator = JsonSchemaValidator(logger=self.logger)
        self.google_workspaceevents_client = (
            self.google_client.create_workspaceevents_client()
        )
        self.subscriber_client = self.google_client.create_subscriber_client()
        self.google_chat_client = self.google_client.create_chat_client()
        self.google_people_client = self.google_client.create_people_client()
        self.jira_client = JiraClient(
            jira_server=jira_server,
            jira_user=jira_user,
            logger=self.logger,
            retry_utils=self.retry_utils,
        ).get_jira_client()
        self.google_calendar_client = self.google_client.create_calendar_client()
        self.google_reports_client = self.google_client.create_reports_client()

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
        self.google_chat_subscription_service = GoogleChatSubscriptionService(
            logger=self.logger,
            retry_utils=self.retry_utils,
            google_workspaceevents_client=self.google_workspaceevents_client,
        )
        self.notification_controller = NotificationController(
            microsoft_chat_subscription_service=self.microsoft_chat_subscription_service,
            google_chat_subscription_service=self.google_chat_subscription_service,
        )
        self.date_time_util = DateTimeUtil(logger=self.logger)
        self.microsoft_chat_message_util = MicrosoftChatMessageUtil(
            logger=self.logger,
            redis_client=self.redis_client,
            microsoft_service=self.microsoft_service,
            date_time_util=self.date_time_util,
            retry_utils=self.retry_utils,
        )
        self.gerrit_sync_service = GerritSyncService(
            logger=self.logger,
            redis_client=self.redis_client,
            gerrit_client=self.gerrit_client,
            retry_utils=self.retry_utils,
            date_time_util=self.date_time_util,
        )
        self.asyncio_event_loop_manager = AsyncioEventLoopManager()

        self.pubsub_puller_factory = PubSubPullerFactory(
            puller_creator=PubSubPuller,
            logger=self.logger,
            redis_client=self.redis_client,
            subscriber_client=self.subscriber_client,
            asyncio_event_loop_manager=self.asyncio_event_loop_manager,
        )
        self.pubsub_pull_manager = PubSubPullManager(
            pubsub_puller_factory=self.pubsub_puller_factory
        )
        self.microsoft_message_processor_service = MicrosoftMessageProcessorService(
            logger=self.logger,
            pubsub_puller_factory=self.pubsub_puller_factory,
            microsoft_chat_message_util=self.microsoft_chat_message_util,
        )
        self.google_chat_messages_utils = GoogleChatMessagesUtils(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
        )
        self.google_service = GoogleService(
            logger=self.logger,
            google_chat_client=self.google_chat_client,
            google_people_client=self.google_people_client,
            google_workspaceevents_client=self.google_workspaceevents_client,
            retry_utils=self.retry_utils,
        )
        self.google_chat_processor_service = GoogleChatProcessorService(
            logger=self.logger,
            pubsub_puller_factory=self.pubsub_puller_factory,
            google_chat_messages_utils=self.google_chat_messages_utils,
            google_service=self.google_service,
        )
        self.gerrit_processor_service = GerritProcessorService(
            logger=self.logger,
            redis_client=self.redis_client,
            pubsub_puller_factory=self.pubsub_puller_factory,
            retry_utils=self.retry_utils,
            date_time_util=self.date_time_util,
            gerrit_client=self.gerrit_client,
        )
        self.consumer_controller = ConsumerController(
            microsoft_message_processor_service=self.microsoft_message_processor_service,
            google_chat_processor_service=self.google_chat_processor_service,
            gerrit_processor_service=self.gerrit_processor_service,
            pubsub_pull_manager=self.pubsub_pull_manager,
        )

        self.microsoft_member_sync_service = MicrosoftMemberSyncService(
            logger=self.logger,
            redis_client=self.redis_client,
            microsoft_service=self.microsoft_service,
            retry_utils=self.retry_utils,
        )
        self.microsoft_chat_history_sync_service = MicrosoftChatHistorySyncService(
            logger=self.logger,
            microsoft_service=self.microsoft_service,
            microsoft_chat_message_util=self.microsoft_chat_message_util,
        )
        self.jira_search_service = JiraSearchService(
            logger=self.logger,
            jira_client=self.jira_client,
            retry_utils=self.retry_utils,
        )
        self.jira_history_sync_service = JiraHistorySyncService(
            logger=self.logger,
            redis_client=self.redis_client,
            jira_client=self.jira_client,
            jira_search_service=self.jira_search_service,
            date_time_util=self.date_time_util,
            retry_utils=self.retry_utils,
        )
        self.ldap_service = LdapService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
        )
        self.google_calendar_sync_service = GoogleCalendarSyncService(
            logger=self.logger,
            redis_client=self.redis_client,
            google_calendar_client=self.google_calendar_client,
            google_reports_client=self.google_reports_client,
            retry_utils=self.retry_utils,
            json_schema_validator=self.json_schema_validator,
            google_service=self.google_service,
        )
        self.google_chat_history_sync_service = GoogleChatHistorySyncService(
            logger=self.logger,
            google_service=self.google_service,
            google_chat_message_utils=self.google_chat_messages_utils,
        )
        self.historical_controller = HistoricalController(
            microsoft_member_sync_service=self.microsoft_member_sync_service,
            microsoft_chat_history_sync_service=self.microsoft_chat_history_sync_service,
            jira_history_sync_service=self.jira_history_sync_service,
            google_calendar_sync_service=self.google_calendar_sync_service,
            date_time_utils=self.date_time_util,
            gerrit_sync_service=self.gerrit_sync_service,
            google_chat_history_sync_service=self.google_chat_history_sync_service,
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
        self.jira_analytics_service = JiraAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            date_time_util=self.date_time_util,
            ldap_service=self.ldap_service,
        )
        self.google_calendar_analytics_service = GoogleCalendarAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
        )
        self.gerrit_analytics_service = GerritAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            ldap_service=self.ldap_service,
            date_time_util=self.date_time_util,
            gerrit_client=self.gerrit_client,
        )
        self.google_chat_analytics_service = GoogleChatAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            date_time_util=self.date_time_util,
            google_service=self.google_service,
            ldap_service=self.ldap_service,
        )
        self.summary_service = SummaryService(
            ldap_service=self.ldap_service,
            microsoft_chat_analytics_service=self.microsoft_chat_analytics_service,
            google_calendar_analytics_service=self.google_calendar_analytics_service,
            google_chat_analytics_service=self.google_chat_analytics_service,
            gerrit_analytics_service=self.gerrit_analytics_service,
            jira_analytics_service=self.jira_analytics_service,
            date_time_util=self.date_time_util,
        )
        self.frontend_controller = FrontendController(
            ldap_service=self.ldap_service,
            microsoft_chat_analytics_service=self.microsoft_chat_analytics_service,
            microsoft_meeting_chat_topic_cache_service=self.microsoft_meeting_chat_topic_cache_service,
            jira_analytics_service=self.jira_analytics_service,
            google_calendar_analytics_service=self.google_calendar_analytics_service,
            date_time_util=self.date_time_util,
            gerrit_analytics_service=self.gerrit_analytics_service,
            google_chat_analytics_service=self.google_chat_analytics_service,
            summary_service=self.summary_service,
        )
        self.authentication_service = AuthenticationService(logger=self.logger)
        self.authentication_controller = AuthenticationController()
        self.fast_app_factory = FastAppFactory(
            authentication_controller=self.authentication_controller,
            authentication_service=self.authentication_service,
            notification_controller=self.notification_controller,
        )
        self.users_repository = UsersRepository()
        self.experience_repository = ExperienceRepository()
        self.training_repository = TrainingRepository()
        self.profile_mapper = ProfileMapper()
        self.profile_query_service = ProfileQueryService(
            users_repository=self.users_repository,
            experience_repository=self.experience_repository,
            training_repository=self.training_repository,
            profile_mapper=self.profile_mapper,
        )
        self.profile_command_service = ProfileCommandService(
            users_repository=self.users_repository, logger=self.logger
        )
