from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from backend.utils.app_dependency_builder import AppDependencyBuilder
from backend.common.environment_constants import (
    JIRA_SERVER,
    JIRA_USER,
)


@patch("backend.utils.app_dependency_builder.SummaryService")
@patch("backend.utils.app_dependency_builder.PubSubPullManager")
@patch("backend.utils.app_dependency_builder.AsyncioEventLoopManager")
@patch("backend.utils.app_dependency_builder.GoogleChatHistorySyncService")
@patch("backend.utils.app_dependency_builder.GoogleChatAnalyticsService")
@patch("backend.utils.app_dependency_builder.GerritProcessorService")
@patch("backend.utils.app_dependency_builder.GerritSyncService")
@patch("backend.utils.app_dependency_builder.GerritClient")
@patch("backend.utils.app_dependency_builder.GerritAnalyticsService")
@patch("backend.utils.app_dependency_builder.JsonSchemaValidator")
@patch("backend.utils.app_dependency_builder.GoogleCalendarSyncService")
@patch("backend.utils.app_dependency_builder.GoogleChatProcessorService")
@patch("backend.utils.app_dependency_builder.GoogleService")
@patch("backend.utils.app_dependency_builder.GoogleChatMessagesUtils")
@patch("backend.utils.app_dependency_builder.GoogleCalendarAnalyticsService")
@patch("backend.utils.app_dependency_builder.JiraAnalyticsService")
@patch("backend.utils.app_dependency_builder.MicrosoftChatHistorySyncService")
@patch("backend.utils.app_dependency_builder.JiraSearchService")
@patch("backend.utils.app_dependency_builder.MicrosoftMeetingChatTopicCacheService")
@patch("backend.utils.app_dependency_builder.MicrosoftChatAnalyticsService")
@patch("backend.utils.app_dependency_builder.LdapService")
@patch("backend.utils.app_dependency_builder.FrontendController")
@patch("backend.utils.app_dependency_builder.MicrosoftMemberSyncService")
@patch("backend.utils.app_dependency_builder.HistoricalController")
@patch("backend.utils.app_dependency_builder.ConsumerController")
@patch("backend.utils.app_dependency_builder.MicrosoftMessageProcessorService")
@patch("backend.utils.app_dependency_builder.PubSubPullerFactory")
@patch("backend.utils.app_dependency_builder.PubSubPuller")
@patch("backend.utils.app_dependency_builder.MicrosoftChatMessageUtil")
@patch("backend.utils.app_dependency_builder.DateTimeUtil")
@patch("backend.utils.app_dependency_builder.NotificationController")
@patch("backend.utils.app_dependency_builder.GoogleChatSubscriptionService")
@patch("backend.utils.app_dependency_builder.MicrosoftChatSubscriptionService")
@patch("backend.utils.app_dependency_builder.MicrosoftService")
@patch("backend.utils.app_dependency_builder.GoogleClient")
@patch("backend.utils.app_dependency_builder.MicrosoftGraphServiceClient")
@patch("backend.utils.app_dependency_builder.RedisClient")
@patch("backend.utils.app_dependency_builder.get_logger")
@patch("backend.utils.app_dependency_builder.RetryUtils")
@patch("backend.utils.app_dependency_builder.JiraClient")
@patch("backend.utils.app_dependency_builder.JiraHistorySyncService")
@patch("os.getenv")
class TestAppDependencyBuilder(TestCase):
    def test_dependencies_are_wired_correctly(
        self,
        mock_os_getenv,
        mock_jira_history_cls,
        mock_jira_client_cls,
        mock_retry_utils_cls,
        mock_get_logger,
        mock_redis_client_cls,
        mock_graph_service_client_cls,
        mock_google_client_cls,
        mock_microsoft_service,
        mock_microsoft_chat_subscription_service,
        mock_google_chat_subscription_service,
        mock_notification_controller,
        mock_date_time_util_cls,
        mock_microsoft_chat_message_util_cls,
        mock_pubsub_puller_cls,
        mock_pubsub_puller_factory_cls,
        mock_microsoft_message_processor_service_cls,
        mock_consumer_controller_cls,
        mock_historical_controller_cls,
        mock_microsoft_member_sync_service_cls,
        mock_frontend_controller_cls,
        mock_ldap_service_cls,
        mock_microsoft_chat_analytics_service_cls,
        mock_microsoft_meeting_chat_topic_cache_service_cls,
        mock_jira_search_service_cls,
        mock_microsoft_chat_history_sync_service_cls,
        mock_jira_analytics_service_cls,
        mock_google_calendar_analytics_service_cls,
        mock_google_chat_messages_utils,
        mock_google_service,
        mock_google_chat_processor_service,
        mock_google_calendar_sync_service_cls,
        mock_json_schema_validator_cls,
        mock_gerrit_analytics_service_cls,
        mock_gerrit_client_cls,
        mock_gerrit_sync_service_cls,
        mock_gerrit_processor_service_cls,
        mock_google_chat_analytics_service_cls,
        mock_google_chat_history_sync_service_cls,
        mock_asyncio_event_loop_manager_cls,
        mock_pubsub_pull_manager_cls,
        mock_summary_service_cls,
    ):
        """
        Tests that the AppDependencyBuilder correctly instantiates and wires all its dependencies.
        """
        # Arrange: Setup mock return values for all factories and constructors
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        mock_redis_client = MagicMock()
        mock_redis_client_instance = MagicMock()
        mock_redis_client_instance.get_redis_client.return_value = mock_redis_client
        mock_redis_client_cls.return_value = mock_redis_client_instance
        mock_graph_client = MagicMock()
        mock_graph_service_client_instance = MagicMock()
        mock_graph_service_client_instance.get_graph_service_client = mock_graph_client
        mock_graph_service_client_cls.return_value = mock_graph_service_client_instance
        mock_google_workspaceevents_client = MagicMock()
        mock_google_client_instance = MagicMock()
        mock_google_chat_client = MagicMock()
        mock_google_people_client = MagicMock()
        mock_google_subscriber_client = MagicMock()
        mock_google_client_instance.create_subscriber_client.return_value = (
            mock_google_subscriber_client
        )
        mock_google_client_instance.create_workspaceevents_client.return_value = (
            mock_google_workspaceevents_client
        )
        mock_google_client_instance.create_chat_client.return_value = (
            mock_google_chat_client
        )
        mock_google_client_instance.create_people_client.return_value = (
            mock_google_people_client
        )
        mock_google_calendar_client = MagicMock()
        mock_google_client_instance.create_calendar_client.return_value = (
            mock_google_calendar_client
        )
        mock_google_reports_client = MagicMock()
        mock_google_client_instance.create_reports_client.return_value = (
            mock_google_reports_client
        )
        mock_google_client_cls.return_value = mock_google_client_instance
        mock_asyncio_event_loop_manager = MagicMock()
        mock_asyncio_event_loop_manager_cls.return_value = (
            mock_asyncio_event_loop_manager
        )
        mock_google_client_cls.return_value = mock_google_client_instance
        mock_retry_utils_instance = MagicMock()
        mock_retry_utils_cls.return_value = mock_retry_utils_instance
        mock_jira_client_instance = MagicMock()
        mock_jira_client_cls.return_value.get_jira_client.return_value = (
            mock_jira_client_instance
        )
        mock_jira_client = mock_jira_client_cls.return_value.get_jira_client()
        mock_jira_history_service = mock_jira_history_cls.return_value
        mock_json_schema_validator_instance = MagicMock()
        mock_json_schema_validator_cls.return_value = (
            mock_json_schema_validator_instance
        )

        # Configure os.getenv mock for JiraClient
        JIRA_SERVER_VAL = "https://test-jira.com"
        JIRA_USER_VAL = "testuser"

        mock_os_getenv.side_effect = lambda key: {
            JIRA_SERVER: JIRA_SERVER_VAL,
            JIRA_USER: JIRA_USER_VAL,
        }.get(key)

        mock_gerrit_client = mock_gerrit_client_cls.return_value
        mock_gerrit_sync_service = mock_gerrit_sync_service_cls.return_value
        mock_google_chat_history_sync_service = (
            mock_google_chat_history_sync_service_cls.return_value
        )

        # Act: Instantiate the builder, which should trigger all dependency creation
        builder = AppDependencyBuilder()

        # Assert: Verify that all factories and constructors were called correctly
        mock_get_logger.assert_called_once()
        mock_redis_client_cls.assert_called_once()
        mock_redis_client_instance.get_redis_client.assert_called_once()
        mock_graph_service_client_cls.assert_called_once()
        mock_google_client_cls.assert_called_once()
        mock_google_client_instance.create_workspaceevents_client.assert_called_once()
        mock_google_client_instance.create_calendar_client.assert_called_once()
        mock_google_client_instance.create_reports_client.assert_called_once()
        mock_retry_utils_cls.assert_called_once()
        mock_gerrit_client_cls.assert_called_once()
        mock_jira_client_cls.assert_called_once()

        mock_microsoft_service.assert_called_once_with(
            logger=mock_logger,
            graph_service_client=mock_graph_client,
            retry_utils=mock_retry_utils_instance,
        )
        mock_microsoft_chat_subscription_service.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            microsoft_service=mock_microsoft_service.return_value,
        )
        mock_google_chat_subscription_service.assert_called_once_with(
            logger=mock_logger,
            google_workspaceevents_client=mock_google_workspaceevents_client,
            retry_utils=mock_retry_utils_instance,
        )
        mock_notification_controller.assert_called_once_with(
            microsoft_chat_subscription_service=mock_microsoft_chat_subscription_service.return_value,
            google_chat_subscription_service=mock_google_chat_subscription_service.return_value,
        )
        mock_date_time_util_cls.assert_called_once_with(logger=mock_logger)

        mock_microsoft_chat_message_util_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            microsoft_service=mock_microsoft_service.return_value,
            date_time_util=mock_date_time_util_cls.return_value,
            retry_utils=mock_retry_utils_instance,
        )

        mock_pubsub_puller_factory_cls.assert_called_once_with(
            puller_creator=mock_pubsub_puller_cls,
            logger=mock_logger,
            redis_client=mock_redis_client,
            subscriber_client=mock_google_subscriber_client,
            asyncio_event_loop_manager=mock_asyncio_event_loop_manager,
        )

        mock_pubsub_pull_manager_cls.assert_called_once_with(
            pubsub_puller_factory=mock_pubsub_puller_factory_cls.return_value,
        )

        mock_microsoft_message_processor_service_cls.assert_called_once_with(
            logger=mock_logger,
            pubsub_puller_factory=mock_pubsub_puller_factory_cls.return_value,
            microsoft_chat_message_util=mock_microsoft_chat_message_util_cls.return_value,
        )

        mock_gerrit_processor_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            pubsub_puller_factory=mock_pubsub_puller_factory_cls.return_value,
            retry_utils=mock_retry_utils_instance,
            date_time_util=mock_date_time_util_cls.return_value,
        )

        mock_consumer_controller_cls.assert_called_once_with(
            microsoft_message_processor_service=mock_microsoft_message_processor_service_cls.return_value,
            google_chat_processor_service=mock_google_chat_processor_service.return_value,
            gerrit_processor_service=mock_gerrit_processor_service_cls.return_value,
            pubsub_pull_manager=mock_pubsub_pull_manager_cls.return_value,
        )

        mock_microsoft_member_sync_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            microsoft_service=mock_microsoft_service.return_value,
            retry_utils=mock_retry_utils_instance,
        )
        mock_microsoft_chat_history_sync_service_cls.assert_called_once_with(
            logger=mock_logger,
            microsoft_service=mock_microsoft_service.return_value,
            microsoft_chat_message_util=mock_microsoft_chat_message_util_cls.return_value,
        )
        mock_jira_search_service_cls.assert_called_once_with(
            logger=mock_logger,
            jira_client=mock_jira_client,
            retry_utils=mock_retry_utils_instance,
        )
        mock_jira_history_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            jira_client=mock_jira_client,
            jira_search_service=mock_jira_search_service_cls.return_value,
            date_time_util=mock_date_time_util_cls.return_value,
            retry_utils=mock_retry_utils_instance,
        )
        mock_google_calendar_sync_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            google_calendar_client=mock_google_calendar_client,
            google_reports_client=mock_google_reports_client,
            retry_utils=mock_retry_utils_instance,
            json_schema_validator=mock_json_schema_validator_cls.return_value,
            google_service=mock_google_service.return_value,
        )
        mock_gerrit_sync_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            gerrit_client=mock_gerrit_client,
            retry_utils=mock_retry_utils_instance,
            date_time_util=mock_date_time_util_cls.return_value,
        )
        mock_google_chat_history_sync_service_cls.assert_called_once_with(
            logger=mock_logger,
            google_service=mock_google_service.return_value,
            google_chat_message_utils=mock_google_chat_messages_utils.return_value,
        )
        mock_historical_controller_cls.assert_called_once_with(
            microsoft_member_sync_service=mock_microsoft_member_sync_service_cls.return_value,
            microsoft_chat_history_sync_service=mock_microsoft_chat_history_sync_service_cls.return_value,
            jira_history_sync_service=mock_jira_history_service,
            google_calendar_sync_service=mock_google_calendar_sync_service_cls.return_value,
            date_time_utils=mock_date_time_util_cls.return_value,
            gerrit_sync_service=mock_gerrit_sync_service,
            google_chat_history_sync_service=mock_google_chat_history_sync_service,
        )
        mock_ldap_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            retry_utils=mock_retry_utils_instance,
        )
        mock_microsoft_chat_analytics_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            date_time_util=mock_date_time_util_cls.return_value,
            ldap_service=mock_ldap_service_cls.return_value,
            retry_utils=mock_retry_utils_instance,
        )
        mock_microsoft_meeting_chat_topic_cache_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            microsoft_service=mock_microsoft_service.return_value,
            retry_utils=mock_retry_utils_instance,
        )
        mock_jira_analytics_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            retry_utils=mock_retry_utils_instance,
            date_time_util=mock_date_time_util_cls.return_value,
            ldap_service=mock_ldap_service_cls.return_value,
        )
        mock_google_calendar_analytics_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            retry_utils=mock_retry_utils_instance,
        )
        mock_gerrit_analytics_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            retry_utils=mock_retry_utils_instance,
            ldap_service=mock_ldap_service_cls.return_value,
            date_time_util=mock_date_time_util_cls.return_value,
        )
        mock_google_chat_analytics_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            retry_utils=mock_retry_utils_instance,
            date_time_util=mock_date_time_util_cls.return_value,
            google_service=mock_google_service.return_value,
            ldap_service=mock_ldap_service_cls.return_value,
        )
        mock_summary_service_cls.assert_called_once_with(
            ldap_service=mock_ldap_service_cls.return_value,
            microsoft_chat_analytics_service=mock_microsoft_chat_analytics_service_cls.return_value,
            google_calendar_analytics_service=mock_google_calendar_analytics_service_cls.return_value,
            google_chat_analytics_service=mock_google_chat_analytics_service_cls.return_value,
            gerrit_analytics_service=mock_gerrit_analytics_service_cls.return_value,
            jira_analytics_service=mock_jira_analytics_service_cls.return_value,
            date_time_util=mock_date_time_util_cls.return_value,
        )

        # Assert that the builder's internal attributes are the created mock instances
        mock_google_client_instance.create_chat_client.assert_called_once()
        mock_google_client_instance.create_people_client.assert_called_once()

        mock_google_chat_messages_utils.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            retry_utils=mock_retry_utils_instance,
        )

        mock_google_service.assert_called_once_with(
            logger=mock_logger,
            google_chat_client=mock_google_chat_client,
            google_people_client=mock_google_people_client,
            google_workspaceevents_client=mock_google_workspaceevents_client,
            retry_utils=mock_retry_utils_instance,
        )

        mock_google_chat_processor_service.assert_called_once_with(
            logger=mock_logger,
            pubsub_puller_factory=mock_pubsub_puller_factory_cls.return_value,
            google_chat_messages_utils=mock_google_chat_messages_utils.return_value,
            google_service=mock_google_service.return_value,
        )

        mock_google_chat_analytics_service_cls.assert_called_once_with(
            logger=mock_logger,
            redis_client=mock_redis_client,
            retry_utils=mock_retry_utils_instance,
            date_time_util=mock_date_time_util_cls.return_value,
            google_service=mock_google_service.return_value,
            ldap_service=mock_ldap_service_cls.return_value,
        )

        mock_frontend_controller_cls.assert_called_once_with(
            ldap_service=mock_ldap_service_cls.return_value,
            microsoft_chat_analytics_service=mock_microsoft_chat_analytics_service_cls.return_value,
            microsoft_meeting_chat_topic_cache_service=mock_microsoft_meeting_chat_topic_cache_service_cls.return_value,
            jira_analytics_service=mock_jira_analytics_service_cls.return_value,
            google_calendar_analytics_service=mock_google_calendar_analytics_service_cls.return_value,
            date_time_util=mock_date_time_util_cls.return_value,
            gerrit_analytics_service=mock_gerrit_analytics_service_cls.return_value,
            google_chat_analytics_service=mock_google_chat_analytics_service_cls.return_value,
            summary_service=mock_summary_service_cls.return_value,
        )

        # Assert that the builder's internal attributes are the created mock instances
        self.assertEqual(builder.logger, mock_logger)
        self.assertEqual(builder.redis_client, mock_redis_client)
        self.assertEqual(builder.gerrit_client, mock_gerrit_client)
        self.assertEqual(builder.graph_client, mock_graph_client)
        self.assertEqual(
            builder.google_workspaceevents_client, mock_google_workspaceevents_client
        )
        self.assertEqual(builder.retry_utils, mock_retry_utils_instance)
        self.assertEqual(
            builder.json_schema_validator, mock_json_schema_validator_instance
        )
        self.assertEqual(builder.microsoft_service, mock_microsoft_service.return_value)
        self.assertEqual(
            builder.microsoft_chat_subscription_service,
            mock_microsoft_chat_subscription_service.return_value,
        )
        self.assertEqual(builder.google_client, mock_google_client_instance)
        self.assertEqual(
            builder.google_workspaceevents_client, mock_google_workspaceevents_client
        )
        self.assertEqual(builder.google_chat_client, mock_google_chat_client)
        self.assertEqual(builder.google_people_client, mock_google_people_client)
        self.assertEqual(
            builder.google_chat_messages_utils,
            mock_google_chat_messages_utils.return_value,
        )
        self.assertEqual(
            builder.google_chat_processor_service,
            mock_google_chat_processor_service.return_value,
        )
        self.assertEqual(builder.google_service, mock_google_service.return_value)
        self.assertEqual(
            builder.google_chat_subscription_service,
            mock_google_chat_subscription_service.return_value,
        )
        self.assertEqual(
            builder.notification_controller, mock_notification_controller.return_value
        )
        self.assertEqual(builder.date_time_util, mock_date_time_util_cls.return_value)
        self.assertEqual(
            builder.microsoft_chat_message_util,
            mock_microsoft_chat_message_util_cls.return_value,
        )
        self.assertEqual(
            builder.pubsub_puller_factory, mock_pubsub_puller_factory_cls.return_value
        )
        self.assertEqual(
            builder.microsoft_message_processor_service,
            mock_microsoft_message_processor_service_cls.return_value,
        )
        self.assertEqual(
            builder.gerrit_processor_service,
            mock_gerrit_processor_service_cls.return_value,
        )
        self.assertEqual(
            builder.consumer_controller, mock_consumer_controller_cls.return_value
        )
        self.assertEqual(
            builder.microsoft_member_sync_service,
            mock_microsoft_member_sync_service_cls.return_value,
        )
        self.assertEqual(
            builder.microsoft_chat_history_sync_service,
            mock_microsoft_chat_history_sync_service_cls.return_value,
        )
        self.assertEqual(
            builder.google_calendar_sync_service,
            mock_google_calendar_sync_service_cls.return_value,
        )
        self.assertEqual(
            builder.historical_controller, mock_historical_controller_cls.return_value
        )
        self.assertEqual(
            builder.ldap_service,
            mock_ldap_service_cls.return_value,
        )
        self.assertEqual(
            builder.microsoft_chat_analytics_service,
            mock_microsoft_chat_analytics_service_cls.return_value,
        )
        self.assertEqual(
            builder.jira_analytics_service,
            mock_jira_analytics_service_cls.return_value,
        )
        self.assertEqual(
            builder.google_calendar_analytics_service,
            mock_google_calendar_analytics_service_cls.return_value,
        )
        self.assertEqual(
            builder.gerrit_analytics_service,
            mock_gerrit_analytics_service_cls.return_value,
        )
        self.assertEqual(
            builder.google_chat_analytics_service,
            mock_google_chat_analytics_service_cls.return_value,
        )
        self.assertEqual(builder.summary_service, mock_summary_service_cls.return_value)
        self.assertEqual(
            builder.frontend_controller, mock_frontend_controller_cls.return_value
        )
        self.assertEqual(
            builder.microsoft_meeting_chat_topic_cache_service,
            mock_microsoft_meeting_chat_topic_cache_service_cls.return_value,
        )
        self.assertEqual(builder.jira_client, mock_jira_client)
        self.assertEqual(builder.jira_history_sync_service, mock_jira_history_service)


if __name__ == "__main__":
    main()
