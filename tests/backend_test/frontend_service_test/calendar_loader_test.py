from unittest import TestCase, main
from unittest.mock import patch, Mock
from backend.frontend_service.calendar_loader import (
    get_all_calendars,
)


class TestCalendarLoader(TestCase):
    @patch(
        "backend.frontend_service.calendar_loader.RedisClientFactory.create_redis_client"
    )
    def test_get_all_calendars_success(self, mock_create_redis_client):
        mock_redis = Mock()
        mock_redis.hgetall.return_value = {
            "calendar_id_1": "Work",
            "calendar_id_2": "Personal",
        }
        mock_create_redis_client.return_value = mock_redis

        expected_result = [
            {"id": "calendar_id_1", "name": "Work"},
            {"id": "calendar_id_2", "name": "Personal"},
        ]

        result = get_all_calendars()
        self.assertEqual(result, expected_result)

    @patch(
        "backend.frontend_service.calendar_loader.RedisClientFactory.create_redis_client"
    )
    def test_get_all_calendars_empty(self, mock_create_redis_client):
        mock_redis = Mock()
        mock_redis.hgetall.return_value = {}
        mock_create_redis_client.return_value = mock_redis

        result = get_all_calendars()
        self.assertEqual(result, [])

    @patch(
        "backend.frontend_service.calendar_loader.RedisClientFactory.create_redis_client"
    )
    def test_get_all_calendars_redis_client_none(self, mock_create_redis_client):
        mock_create_redis_client.return_value = None
        with self.assertRaises(ValueError):
            get_all_calendars()


if __name__ == "__main__":
    main()
