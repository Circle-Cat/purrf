from unittest import TestCase, main
from unittest.mock import patch, Mock
from backend.frontend_service.calendar_loader import (
    get_all_calendars,
    get_all_events,
)
import json


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

    @patch(
        "backend.frontend_service.calendar_loader.RedisClientFactory.create_redis_client"
    )
    def test_get_all_events_success(self, mock_create_redis_client):
        mock_redis = Mock()
        mock_pipeline = Mock()

        calendar_id = "personal"
        ldaps = ["user1"]
        start_date = "2025-07-01T00:00:00"
        end_date = "2025-08-02T00:00:00"

        mock_pipeline.execute.side_effect = [
            [["event123"]],  # zrangebyscore result
            [
                json.dumps([  # attendance get result
                    {
                        "join_time": "2025-08-01T10:00:00",
                        "leave_time": "2025-08-01T10:30:00",
                    },
                    {
                        "join_time": "2025-08-01T11:00:00",
                        "leave_time": "2025-08-01T11:45:00",
                    },
                ])
            ],
            [
                json.dumps({  # event detail get result
                    "summary": "Team Sync",
                    "calendar_id": "personal",
                    "is_recurring": True,
                })
            ],
        ]

        mock_redis.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis

        expected_result = {
            "user1": [
                {
                    "event_id": "event123",
                    "summary": "Team Sync",
                    "calendar_id": "personal",
                    "is_recurring": True,
                    "attendance": [
                        {
                            "join_time": "2025-08-01T10:00:00",
                            "leave_time": "2025-08-01T10:30:00",
                        },
                        {
                            "join_time": "2025-08-01T11:00:00",
                            "leave_time": "2025-08-01T11:45:00",
                        },
                    ],
                }
            ]
        }

        result = get_all_events(calendar_id, ldaps, start_date, end_date)
        self.assertEqual(result, expected_result)


if __name__ == "__main__":
    main()
