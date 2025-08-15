from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from backend.utils.app_dependency_builder import AppDependencyBuilder


@patch("backend.utils.app_dependency_builder.NotificationController")
@patch("backend.utils.app_dependency_builder.MicrosoftChatSubscriptionService")
@patch("backend.utils.app_dependency_builder.MicrosoftService")
@patch("backend.utils.app_dependency_builder.MicrosoftGraphServiceClient")
@patch("backend.utils.app_dependency_builder.RedisClientFactory")
@patch("backend.utils.app_dependency_builder.get_logger")
@patch("backend.utils.app_dependency_builder.RetryUtils")
class TestAppDependencyBuilder(TestCase):
    def test_dependencies_are_wired_correctly(
        self,
        mock_retry_utils_cls,
        mock_get_logger,
        mock_redis_client_factory_cls,
        mock_graph_service_client_cls,
        mock_microsoft_service,
        mock_microsoft_chat_subscription_service,
        mock_notification_controller,
    ):
        """
        Tests that the AppDependencyBuilder correctly instantiates and wires all its dependencies.
        """
        # Arrange: Setup mock return values for all factories and constructors
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        mock_redis_client = MagicMock()
        mock_redis_client_factory_instance = MagicMock()
        mock_redis_client_factory_instance.create_redis_client.return_value = (
            mock_redis_client
        )
        mock_redis_client_factory_cls.return_value = mock_redis_client_factory_instance
        mock_graph_client = MagicMock()
        mock_graph_service_client_instance = MagicMock()
        mock_graph_service_client_instance.get_graph_service_client = mock_graph_client
        mock_graph_service_client_cls.return_value = mock_graph_service_client_instance
        mock_retry_utils_instance = MagicMock()
        mock_retry_utils_cls.return_value = mock_retry_utils_instance

        # Act: Instantiate the builder, which should trigger all dependency creation
        builder = AppDependencyBuilder()

        # Assert: Verify that all factories and constructors were called correctly
        mock_get_logger.assert_called_once()
        mock_redis_client_factory_cls.assert_called_once()
        mock_redis_client_factory_instance.create_redis_client.assert_called_once()
        mock_graph_service_client_cls.assert_called_once()
        mock_retry_utils_cls.assert_called_once()

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

        mock_notification_controller.assert_called_once_with(
            microsoft_chat_subscription_service=mock_microsoft_chat_subscription_service.return_value
        )

        # Assert that the builder's internal attributes are the created mock instances
        self.assertEqual(builder.logger, mock_logger)
        self.assertEqual(builder.redis_client, mock_redis_client)
        self.assertEqual(builder.graph_client, mock_graph_client)
        self.assertEqual(builder.retry_utils, mock_retry_utils_instance)
        self.assertEqual(builder.microsoft_service, mock_microsoft_service.return_value)
        self.assertEqual(
            builder.microsoft_chat_subscription_service,
            mock_microsoft_chat_subscription_service.return_value,
        )
        self.assertEqual(
            builder.notification_controller, mock_notification_controller.return_value
        )


if __name__ == "__main__":
    main()
