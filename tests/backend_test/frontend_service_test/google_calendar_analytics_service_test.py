from unittest import TestCase, main
from unittest.mock import Mock
import json
from datetime import datetime
from backend.frontend_service.google_calendar_analytics_service import (
    GoogleCalendarAnalyticsService,
)


class TestGoogleCalendarAnalyticsService(TestCase):
    def setUp(self):
        self.mock_logger = Mock()
        self.mock_redis = Mock()
        self.mock_retry_utils = Mock()
        self.service = GoogleCalendarAnalyticsService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            retry_utils=self.mock_retry_utils,
        )

    def test_get_calendar_name_success(self):
        calendar_id = "personal"
        expected_name = "Personal Calendar"
        self.mock_retry_utils.get_retry_on_transient.return_value = expected_name

        name = self.service._get_calendar_name(calendar_id)

        self.assertEqual(name, expected_name)
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            self.mock_redis.hget, "calendarlist", calendar_id
        )

    def test_get_all_calendars_success(self):
        self.mock_retry_utils.get_retry_on_transient.return_value = {
            "calendar_id_1": "Work",
            "calendar_id_2": "Personal",
        }

        expected_result = [
            {"id": "calendar_id_1", "name": "Work"},
            {"id": "calendar_id_2", "name": "Personal"},
        ]

        result = self.service.get_all_calendars()
        self.assertEqual(result, expected_result)
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            self.mock_redis.hgetall,
            "calendarlist",  # GOOGLE_CALENDAR_LIST_INDEX_KEY
        )

    def test_get_all_calendars_empty(self):
        self.mock_retry_utils.get_retry_on_transient.return_value = {}

        result = self.service.get_all_calendars()
        self.assertEqual(result, [])

    def test_get_all_events_success(self):
        calendar_id = "personal"
        ldaps = ["user1"]
        start_date = datetime.fromisoformat("2025-07-01")
        end_date = datetime.fromisoformat("2025-08-02")

        mock_pipeline = Mock()
        self.mock_redis.pipeline.return_value = mock_pipeline

        self.mock_retry_utils.get_retry_on_transient.side_effect = [
            [["event123"]],
            [
                [
                    json.dumps({
                        "join_time": "2025-08-01T10:00:00",
                        "leave_time": "2025-08-01T10:30:00",
                    }),
                    json.dumps({
                        "join_time": "2025-08-01T11:00:00",
                        "leave_time": "2025-08-01T11:45:00",
                    }),
                ]
            ],
            [
                json.dumps({
                    "summary": "Team Sync",
                    "calendar_id": "personal",
                    "is_recurring": True,
                })
            ],
            "Personal Calendar",
        ]

        expected_result = {
            "user1": [
                {
                    "event_id": "event123",
                    "summary": "Team Sync",
                    "calendar_name": "Personal Calendar",
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

        result = self.service.get_all_events(calendar_id, ldaps, start_date, end_date)
        self.assertEqual(result, expected_result)

        self.assertTrue(self.mock_redis.pipeline.called)
        self.assertTrue(self.mock_retry_utils.get_retry_on_transient.called)

    def test_get_all_events_from_calendars_success(self):
        calendar_ids = ["cal1", "cal2"]
        ldaps = ["user1", "user2"]
        start_date = datetime.fromisoformat("2025-07-01")
        end_date = datetime.fromisoformat("2025-08-02")

        self.service.get_all_events = Mock(
            side_effect=[
                {"user1": [{"event_id": "e1"}], "user2": []},  # cal1
                {"user1": [], "user2": [{"event_id": "e2"}]},  # cal2
            ]
        )

        expected_result = {
            "user1": [{"event_id": "e1"}],
            "user2": [{"event_id": "e2"}],
        }

        result = self.service.get_all_events_from_calendars(
            calendar_ids, ldaps, start_date, end_date
        )
        self.assertEqual(result, expected_result)

        self.service.get_all_events.assert_any_call("cal1", ldaps, start_date, end_date)
        self.service.get_all_events.assert_any_call("cal2", ldaps, start_date, end_date)


if __name__ == "__main__":
    main()
