from unittest import TestCase, main
from unittest.mock import patch, Mock
from backend.frontend_service.calendar_loader import get_calendars_for_user
import json


class TestCalendarLoader(TestCase):
    @patch("backend.common.redis_client.RedisClientFactory.create_redis_client")
    def test_get_calendars_for_user_success(self, mock_create_redis_client):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis

        mock_calendar_ids = ["alice@circlecat.org", "bob@circlecat.org"]
        mock_redis.zrange.return_value = mock_calendar_ids

        mock_pipeline = Mock()
        mock_pipeline.get.side_effect = lambda key: None  # queue the get commands
        mock_pipeline.execute.return_value = [
            json.dumps({
                "calendar_id": "alice@circlecat.org",
                "summary": "Alice Calendar",
            }),
            json.dumps({
                "calendar_id": "bob@circlecat.org",
                "summary": "Bob Calendar",
            }),
        ]

        mock_redis.pipeline.return_value = Mock(
            __enter__=Mock(return_value=mock_pipeline),
            __exit__=Mock(return_value=None),
        )

        result = get_calendars_for_user("purrf")

        expected = [
            {
                "calendar_id": "alice@circlecat.org",
                "summary": "Alice Calendar",
            },
            {
                "calendar_id": "bob@circlecat.org",
                "summary": "Bob Calendar",
            },
        ]

        self.assertEqual(result, expected)
        mock_redis.zrange.assert_called_once_with("user:purrf:calendars", 0, -1)
        self.assertEqual(mock_pipeline.get.call_count, 2)
        mock_pipeline.execute.assert_called_once()

    @patch("backend.common.redis_client.RedisClientFactory.create_redis_client")
    def test_get_calendars_for_user_empty(self, mock_create_redis_client):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis

        mock_redis.zrange.return_value = []
        result = get_calendars_for_user("purrf")
        self.assertEqual(result, [])
        mock_redis.get.assert_not_called()

    @patch("backend.common.redis_client.RedisClientFactory.create_redis_client")
    def test_get_calendars_for_user_redis_client_none(self, mock_create_redis_client):
        mock_create_redis_client.return_value = None
        with self.assertRaises(ValueError):
            get_calendars_for_user("purrf")


if __name__ == "__main__":
    main()
