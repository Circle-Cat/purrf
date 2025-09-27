from unittest import TestCase, main
from unittest.mock import Mock
from backend.consumers.pubsub_puller_factory import PubSubPullerFactory


class TestPubSubPullerFactory(TestCase):
    def setUp(self):
        self.mock_puller_creator = Mock()
        self.logger = Mock()
        self.redis_client = Mock()
        self.subscriber_client = Mock()
        self.asyncio_event_loop_manager = Mock()

        self.factory = PubSubPullerFactory(
            puller_creator=self.mock_puller_creator,
            logger=self.logger,
            redis_client=self.redis_client,
            subscriber_client=self.subscriber_client,
            asyncio_event_loop_manager=self.asyncio_event_loop_manager,
        )

    def test_get_puller_instance_creates_new_instance(self):
        project_id = "test-project-1"
        subscription_id = "test-sub-1"

        mock_puller_instance = Mock(name="PullerInstance1")
        self.mock_puller_creator.return_value = mock_puller_instance

        puller = self.factory.get_puller_instance(project_id, subscription_id)

        self.mock_puller_creator.assert_called_once_with(
            project_id=project_id,
            subscription_id=subscription_id,
            logger=self.logger,
            redis_client=self.redis_client,
            subscriber_client=self.subscriber_client,
            asyncio_event_loop_manager=self.asyncio_event_loop_manager,
        )
        self.assertIs(puller, mock_puller_instance)

    def test_get_puller_instance_returns_cached_instance(self):
        project_id = "test-project-2"
        subscription_id = "test-sub-2"

        mock_puller_instance = Mock(name="PullerInstance2")
        self.mock_puller_creator.return_value = mock_puller_instance

        puller1 = self.factory.get_puller_instance(project_id, subscription_id)
        puller2 = self.factory.get_puller_instance(project_id, subscription_id)

        self.mock_puller_creator.assert_called_once_with(
            project_id=project_id,
            subscription_id=subscription_id,
            logger=self.logger,
            redis_client=self.redis_client,
            subscriber_client=self.subscriber_client,
            asyncio_event_loop_manager=self.asyncio_event_loop_manager,
        )
        self.assertIs(puller1, puller2)
        self.assertIs(puller1, mock_puller_instance)

    def test_get_puller_instance_creates_different_instances_for_different_keys(self):
        project_id_1 = "test-project-3"
        subscription_id_1 = "test-sub-3"

        project_id_2 = "test-project-4"
        subscription_id_2 = "test-sub-4"

        mock_puller_instance_1 = Mock(name="PullerInstance3")
        mock_puller_instance_2 = Mock(name="PullerInstance4")
        self.mock_puller_creator.side_effect = [
            mock_puller_instance_1,
            mock_puller_instance_2,
        ]

        puller1 = self.factory.get_puller_instance(project_id_1, subscription_id_1)
        puller2 = self.factory.get_puller_instance(project_id_2, subscription_id_2)

        self.mock_puller_creator.assert_any_call(
            project_id=project_id_1,
            subscription_id=subscription_id_1,
            logger=self.logger,
            redis_client=self.redis_client,
            subscriber_client=self.subscriber_client,
            asyncio_event_loop_manager=self.asyncio_event_loop_manager,
        )
        self.mock_puller_creator.assert_any_call(
            project_id=project_id_2,
            subscription_id=subscription_id_2,
            logger=self.logger,
            redis_client=self.redis_client,
            subscriber_client=self.subscriber_client,
            asyncio_event_loop_manager=self.asyncio_event_loop_manager,
        )
        self.assertEqual(self.mock_puller_creator.call_count, 2)
        self.assertIsNot(puller1, puller2)
        self.assertIs(puller1, mock_puller_instance_1)
        self.assertIs(puller2, mock_puller_instance_2)
        self.assertEqual(self.logger.info.call_count, 2)

    def test_get_puller_instance_raises_value_error_for_empty_project_id(self):
        with self.assertRaises(ValueError):
            self.factory.get_puller_instance("", "test-sub")
        self.mock_puller_creator.assert_not_called()

    def test_get_puller_instance_raises_value_error_for_empty_subscription_id(self):
        with self.assertRaises(ValueError):
            self.factory.get_puller_instance("test-project", "")
        self.mock_puller_creator.assert_not_called()

    def test_get_puller_instance_raises_value_error_for_none_project_id(self):
        with self.assertRaises(ValueError):
            self.factory.get_puller_instance(None, "test-sub")
        self.mock_puller_creator.assert_not_called()

    def test_get_puller_instance_raises_value_error_for_none_subscription_id(self):
        with self.assertRaises(ValueError):
            self.factory.get_puller_instance("test-project", None)
        self.mock_puller_creator.assert_not_called()


if __name__ == "__main__":
    main()
