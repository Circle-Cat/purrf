from unittest import TestCase, main
from unittest.mock import patch, MagicMock, ANY
from backend.historical_data.google_calendar_history_fetcher import (
    get_calendar_list,
    get_calendar_events,
    get_event_attendance,
    get_meeting_code_from_event,
    cache_calendars,
    cache_events,
    pull_calendar_history,
)
from googleapiclient.errors import HttpError

MOCK_CALENDAR_LIST_PAGE_1 = {
    "items": [
        {
            "id": "cal1",
            "summary": "Work",
        },
        {
            "id": "cal2",
            "summary": "Personal",
        },
    ],
    "nextPageToken": "token123",
}

MOCK_CALENDAR_LIST_PAGE_2 = {
    "items": [
        {
            "id": "cal3",
            "summary": "School",
        }
    ]
}

MOCK_EVENTS_PAGE_1 = {
    "items": [
        {
            "id": "event1",
            "summary": "Engineering Sync",
            "start": {"dateTime": "2025-06-13T10:00:00Z"},
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/abc-defg-hij",
                    }
                ]
            },
        },
        {
            "id": "event2",
            "summary": "One-on-One",
            "start": {"dateTime": "2025-06-13T12:00:00Z"},
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/xyz-1234-pqr",
                    }
                ]
            },
        },
    ],
    "nextPageToken": "token123",
}

MOCK_EVENTS_PAGE_2 = {
    "items": [
        {
            "id": "event3",
            "summary": "Company All-Hands",
            "start": {"dateTime": "2025-06-13T14:00:00Z"},
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/qrs-tuv-wxy",
                    }
                ]
            },
        }
    ]
}

MOCK_REPORTS_RESPONSE = {
    "items": [
        {
            "actor": {"email": "admin@example.com"},
            "events": [
                {
                    "actor": {"email": "user1@circlecat.org"},
                    "type": "call_ended",
                    "parameters": [
                        {"name": "duration_seconds", "intValue": "120"},
                        {"name": "start_timestamp_seconds", "intValue": "1716712800"},
                        {"name": "identifier", "value": "user1@circlecat.org"},
                    ],
                }
            ],
        }
    ]
}

MOCK_EVENT = {
    "conferenceData": {
        "entryPoints": [
            {
                "entryPointType": "video",
                "uri": "https://meet.google.com/abc-def-ghi",
            }
        ]
    }
}


class TestGetCalendarList(TestCase):
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.GoogleClientFactory"
    )
    def test_get_calendar_list_success(self, mock_factory_class):
        mock_service = MagicMock()
        mock_calendar_list = mock_service.calendarList.return_value

        mock_calendar_list.list.return_value.execute.side_effect = [
            MOCK_CALENDAR_LIST_PAGE_1,
            MOCK_CALENDAR_LIST_PAGE_2,
        ]

        mock_factory = MagicMock()
        mock_factory.create_calendar_client.return_value = mock_service
        mock_factory_class.return_value = mock_factory

        calendars = get_calendar_list()

        expected = [
            {
                "calendar_id": "cal1",
                "summary": "Work",
            },
            {
                "calendar_id": "cal2",
                "summary": "Personal",
            },
            {
                "calendar_id": "cal3",
                "summary": "School",
            },
        ]
        self.assertEqual(calendars, expected)

        self.assertEqual(mock_calendar_list.list.call_count, 2)
        mock_factory.create_calendar_client.assert_called_once()

    @patch(
        "backend.historical_data.google_calendar_history_fetcher.GoogleClientFactory"
    )
    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    def test_get_calendar_list_general_exception(self, mock_logger, mock_factory_class):
        mock_factory = MagicMock()
        mock_factory.create_calendar_client.side_effect = Exception("Failed to connect")
        mock_factory_class.return_value = mock_factory

        calendars = get_calendar_list()

        self.assertEqual(calendars, [])
        mock_logger.error.assert_called_with("Unexpected error fetching calendars", ANY)

    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_event_attendance"
    )
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_meeting_code_from_event"
    )
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.GoogleClientFactory"
    )
    def test_get_calendar_events_success(
        self, mock_factory_class, mock_get_meeting_code, mock_get_attendance
    ):
        mock_factory = MagicMock()
        mock_service = MagicMock()
        mock_events = mock_service.events.return_value
        mock_events.list.return_value.execute.side_effect = [
            MOCK_EVENTS_PAGE_1,
            MOCK_EVENTS_PAGE_2,
        ]

        mock_factory.create_calendar_client.return_value = mock_service
        mock_factory_class.return_value = mock_factory

        mock_get_meeting_code.side_effect = [
            "abc-defg-hij",
            "xyz-1234-pqr",
            "qrs-tuv-wxy",
        ]
        mock_get_attendance.return_value = {"attendee_summary": "Present"}

        calendar_id = "test-calendar"
        time_min = "2025-05-01T00:00:00Z"
        time_max = "2025-05-10T00:00:00Z"

        events = get_calendar_events(calendar_id, time_min, time_max)

        expected = [
            {
                "event_id": "event1",
                "calendar_id": "test-calendar",
                "summary": "Engineering Sync",
                "start": "2025-06-13T10:00:00Z",
                "attendees": {"attendee_summary": "Present"},
                "is_recurring": False,
            },
            {
                "event_id": "event2",
                "calendar_id": "test-calendar",
                "summary": "One-on-One",
                "start": "2025-06-13T12:00:00Z",
                "attendees": {"attendee_summary": "Present"},
                "is_recurring": False,
            },
            {
                "event_id": "event3",
                "calendar_id": "test-calendar",
                "summary": "Company All-Hands",
                "start": "2025-06-13T14:00:00Z",
                "attendees": {"attendee_summary": "Present"},
                "is_recurring": False,
            },
        ]

        self.assertEqual(events, expected)
        self.assertEqual(mock_events.list.call_count, 2)

    @patch(
        "backend.historical_data.google_calendar_history_fetcher.GoogleClientFactory",
        side_effect=Exception("Simulated API Failure"),
    )
    def test_get_calendar_events_exception(self, mock_factory):
        calendar_id = "dummy_calendar_id"
        time_min = "2023-01-01T00:00:00Z"
        time_max = "2023-01-31T23:59:59Z"

        with self.assertRaises(Exception) as context:
            get_calendar_events(calendar_id, time_min, time_max)

        self.assertEqual(str(context.exception), "Simulated API Failure")

    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_event_attendance"
    )
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_meeting_code_from_event"
    )
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.GoogleClientFactory"
    )
    def test_get_calendar_events_retries_on_failure_then_succeeds(
        self,
        mock_factory_class,
        mock_get_meeting_code,
        mock_get_attendance,
    ):
        mock_service = MagicMock()
        mock_events = mock_service.events.return_value
        mock_list = mock_events.list.return_value
        mock_execute = mock_list.execute

        mock_execute.side_effect = [
            Exception("Temporary failure 1"),
            Exception("Temporary failure 2"),
            MOCK_EVENTS_PAGE_1,
            MOCK_EVENTS_PAGE_2,
        ]

        mock_factory_instance = mock_factory_class.return_value
        mock_factory_instance.create_calendar_client.return_value = mock_service

        calendar_id = "test_calendar"
        start_time = "2023-01-01T00:00:00Z"
        end_time = "2023-01-02T00:00:00Z"
        mock_get_meeting_code.return_value = "mock-code"
        mock_get_attendance.return_value = {"attendee_summary": "Present"}

        result = get_calendar_events(calendar_id, start_time, end_time)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["event_id"], "event1")
        self.assertEqual(result[1]["event_id"], "event2")
        self.assertEqual(result[2]["event_id"], "event3")
        self.assertEqual(mock_execute.call_count, 4)

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.GoogleClientFactory"
    )
    def test_get_event_attendance_success(self, mock_factory_class, mock_logger):
        mock_factory = MagicMock()
        mock_service = MagicMock()
        mock_activities = mock_service.activities.return_value
        mock_list = mock_activities.list.return_value
        mock_list.execute.return_value = MOCK_REPORTS_RESPONSE

        mock_factory.create_reports_client.return_value = mock_service
        mock_factory_class.return_value = mock_factory

        meeting_code = "abcdefghi"
        attendance = get_event_attendance(meeting_code)

        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance[0]["email"], "user1@circlecat.org")
        self.assertEqual(attendance[0]["duration_seconds"], 120)
        self.assertTrue(
            attendance[0]["join_time"].endswith("Z")
            or "T" in attendance[0]["join_time"]
        )
        self.assertTrue(
            attendance[0]["leave_time"].endswith("Z")
            or "T" in attendance[0]["leave_time"]
        )

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.GoogleClientFactory"
    )
    def test_get_event_attendance_error(self, mock_factory_class, mock_logger):
        mock_factory = MagicMock()
        mock_service = MagicMock()
        mock_activities = mock_service.activities.return_value
        mock_list = mock_activities.list.return_value
        mock_list.execute.side_effect = HttpError(
            resp=MagicMock(status=500), content=b"Internal Error"
        )

        mock_factory.create_reports_client.return_value = mock_service
        mock_factory_class.return_value = mock_factory

        meeting_code = "errorcode"

        with self.assertRaises(HttpError):
            get_event_attendance(meeting_code)

        self.assertEqual(mock_list.execute.call_count, 3)

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.GoogleClientFactory"
    )
    def test_get_event_attendance_retries_then_succeeds(
        self, mock_factory_class, mock_logger
    ):
        mock_factory = MagicMock()
        mock_service = MagicMock()
        mock_activities = mock_service.activities.return_value
        mock_list = mock_activities.list.return_value

        mock_list.execute.side_effect = [
            HttpError(resp=MagicMock(status=500), content=b"Temporary Error"),
            MOCK_REPORTS_RESPONSE,
        ]

        mock_factory.create_reports_client.return_value = mock_service
        mock_factory_class.return_value = mock_factory

        meeting_code = "retry-meeting"
        attendance = get_event_attendance(meeting_code)

        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance[0]["email"], "user1@circlecat.org")
        self.assertEqual(mock_list.execute.call_count, 2)

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    def test_get_meeting_code_from_event_success(self, mock_logger):
        code = get_meeting_code_from_event(MOCK_EVENT)
        self.assertEqual(code, "abcdefghi")

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    def test_get_meeting_code_from_event_no_uri(self, mock_logger):
        event = {"conferenceData": {"entryPoints": []}}
        code = get_meeting_code_from_event(event)
        self.assertIsNone(code)
        mock_logger.warning.assert_called()

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    def test_get_meeting_code_from_event_exception(self, mock_logger):
        event = None
        code = get_meeting_code_from_event(event)
        self.assertIsNone(code)
        mock_logger.exception.assert_called()

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("backend.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("backend.historical_data.google_calendar_history_fetcher.get_calendar_list")
    def test_cache_calendars_success(
        self,
        mock_get_calendar_list,
        mock_validate_data,
        mock_redis_factory,
        mock_logger,
    ):
        mock_get_calendar_list.return_value = [
            {"calendar_id": "user@circlecat.org", "summary": "Personal"},
            {"calendar_id": "team1@group.v.calendar.google.com", "summary": "Team"},
            {"calendar_id": "team2@circlecat.org", "summary": "Team2"},
            {"calendar_id": "valid-calendar@calendar.google.com", "summary": "Valid"},
        ]

        mock_pipeline = MagicMock()
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        cache_calendars()
        mock_pipeline.hset.assert_any_call(
            "calendarlist", "personal", "Personal Calendars"
        )
        mock_pipeline.hset.assert_any_call(
            "calendarlist", "valid-calendar@calendar.google.com", "Valid"
        )
        self.assertTrue(mock_pipeline.execute.called)
        assert mock_validate_data.call_count == 1

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("backend.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("backend.historical_data.google_calendar_history_fetcher.get_calendar_list")
    def test_cache_calendars_no_ldap_found(
        self,
        mock_get_calendar_list,
        mock_validate_data,
        mock_redis_factory,
        mock_logger,
    ):
        mock_get_calendar_list.return_value = [
            {"calendar_id": "team1@group.v.calendar.google.com", "summary": "Team"},
            {"calendar_id": "invalid@calendar.google.com", "summary": "Invalid"},
        ]

        cache_calendars()

        mock_logger.warning.assert_called_with(
            "No calendar_id ending with @circlecat.org found; skipping caching."
        )

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("backend.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("backend.historical_data.google_calendar_history_fetcher.get_calendar_list")
    def test_cache_calendars_invalid_calendar_skipped(
        self,
        mock_get_calendar_list,
        mock_validate_data,
        mock_redis_factory,
        mock_logger,
    ):
        mock_get_calendar_list.return_value = [
            {"calendar_id": "user@circlecat.org", "summary": "Personal"},
            {
                "calendar_id": "invalid-calendar@calendar.google.com",
                "summary": "Invalid",
            },
        ]
        mock_validate_data.side_effect = Exception("schema error")

        mock_pipeline = MagicMock()
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        cache_calendars()

        mock_logger.warning.assert_any_call("Invalid calendar skipped: schema error")
        mock_pipeline.hset.assert_called_once_with(
            "calendarlist", "personal", "Personal Calendars"
        )
        mock_pipeline.execute.assert_called()

    @patch("backend.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("backend.historical_data.google_calendar_history_fetcher.get_calendar_list")
    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    def test_cache_calendars_retries_then_succeeds(
        self, mock_redis_factory, mock_get_calendar_list, mock_validate_data
    ):
        attempts = [
            Exception("temp error"),
            Exception("temp error"),
            [
                {"calendar_id": "user@circlecat.org", "summary": "Personal"},
                {"calendar_id": "valid@calendar.google.com", "summary": "Valid"},
            ],
        ]

        def side_effect():
            result = attempts.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        mock_get_calendar_list.side_effect = side_effect

        mock_pipeline = MagicMock()
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        cache_calendars()

        self.assertTrue(mock_pipeline.execute.called)
        self.assertEqual(mock_get_calendar_list.call_count, 3)

    @patch("backend.historical_data.google_calendar_history_fetcher.get_calendar_list")
    def test_cache_calendars_retries_3_times_and_fails(self, mock_get_calendar_list):
        mock_get_calendar_list.side_effect = Exception("API error")

        with self.assertRaises(Exception):
            cache_calendars()

        self.assertEqual(mock_get_calendar_list.call_count, 3)

    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("backend.historical_data.google_calendar_history_fetcher.validate_data")
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_calendar_events"
    )
    def test_cache_events_success(
        self, mock_get_calendar_events, mock_validate_data, mock_redis_factory
    ):
        mock_get_calendar_events.return_value = [
            {
                "event_id": "event123",
                "summary": "Meeting",
                "start": "2025-07-30T10:00:00",
                "attendees": [
                    {
                        "email": "user1@circlecat.org",
                        "join_time": "2025-07-30T10:00:00",
                        "leave_time": "2025-07-30T10:30:00",
                    }
                ],
            }
        ]

        mock_pipeline = MagicMock()
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis.get.return_value = None
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        updated_ids = cache_events(
            "user@circlecat.org", "2025-07-30T00:00:00", "2025-07-31T00:00:00"
        )

        self.assertIn("event123", updated_ids)
        self.assertTrue(mock_pipeline.set.called)
        self.assertTrue(mock_pipeline.zadd.called)
        self.assertTrue(mock_pipeline.execute.called)

    @patch("backend.historical_data.google_calendar_history_fetcher.logger")
    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("backend.historical_data.google_calendar_history_fetcher.validate_data")
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_calendar_events"
    )
    def test_cache_events_invalid_event_skipped(
        self,
        mock_get_calendar_events,
        mock_validate_data,
        mock_redis_factory,
        mock_logger,
    ):
        mock_get_calendar_events.return_value = [
            {
                "event_id": "event123",
                "summary": "Bad Event",
                "start": "2025-07-30T10:00:00",
                "attendees": [],
            }
        ]
        mock_validate_data.side_effect = Exception("validation failed")

        mock_pipeline = MagicMock()
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        updated_ids = cache_events(
            "user@circlecat.org", "2025-07-30T00:00:00", "2025-07-31T00:00:00"
        )

        self.assertIn("event123", updated_ids)
        mock_logger.warning.assert_any_call("Invalid event skipped: validation failed")
        mock_pipeline.execute.assert_called()

    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("backend.historical_data.google_calendar_history_fetcher.validate_data")
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_calendar_events"
    )
    def test_cache_events_retries_then_succeeds(
        self,
        mock_get_calendar_events,
        mock_validate_data,
        mock_redis_factory,
    ):
        events = [
            {
                "event_id": "event123",
                "summary": "Retry Event",
                "start": "2025-07-30T10:00:00",
                "attendees": [
                    {
                        "email": "user1@circlecat.org",
                        "join_time": "2025-07-30T10:00:00",
                        "leave_time": "2025-07-30T10:30:00",
                    }
                ],
            }
        ]

        attempts = [Exception("temp fail"), Exception("temp fail"), events]

        def side_effect(*args, **kwargs):
            result = attempts.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        mock_get_calendar_events.side_effect = side_effect
        mock_pipeline = MagicMock()
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis.get.return_value = None
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        result = cache_events(
            "user@circlecat.org", "2025-07-30T00:00:00", "2025-07-31T00:00:00"
        )

        self.assertIn("event123", result)
        self.assertEqual(mock_get_calendar_events.call_count, 3)

    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_calendar_events"
    )
    def test_cache_events_fetch_failure_retries(
        self, mock_get_calendar_events, mock_redis_factory
    ):
        mock_get_calendar_events.side_effect = Exception("API failure")

        with self.assertRaises(Exception):
            cache_events(
                "alice@circlecat.org", "2025-06-01T00:00:00Z", "2025-06-30T23:59:59Z"
            )

        self.assertEqual(mock_get_calendar_events.call_count, 3)

    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_all_active_ldap_users"
    )
    @patch("backend.historical_data.google_calendar_history_fetcher.cache_calendars")
    @patch("backend.historical_data.google_calendar_history_fetcher.cache_events")
    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    def test_pull_calendar_history_success(
        self,
        mock_redis_factory,
        mock_cache_events,
        mock_cache_calendars,
        mock_get_ldaps,
    ):
        mock_redis = MagicMock()
        mock_redis.hkeys.return_value = [
            "team1@group.v.calendar.google.com",
            "team2@group.v.calendar.google.com",
        ]
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis
        mock_cache_events.return_value = {"event1", "event2"}
        mock_get_ldaps.return_value = ["user1", "user2"]

        pull_calendar_history("2025-07-01T00:00:00", "2025-08-01T00:00:00")

        self.assertEqual(mock_cache_events.call_count, 4)  # 2 team + 2 personal
        mock_cache_calendars.assert_called_once()
        mock_get_ldaps.assert_called_once()

    @patch("backend.historical_data.google_calendar_history_fetcher.cache_calendars")
    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    def test_pull_calendar_history_no_redis_client(
        self,
        mock_redis_factory,
        mock_cache_calendars,
    ):
        mock_redis_factory.return_value.create_redis_client.return_value = None

        with self.assertRaises(RuntimeError) as ctx:
            pull_calendar_history()

        self.assertIn("Redis client not available", str(ctx.exception))

    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_all_active_ldap_users"
    )
    @patch("backend.historical_data.google_calendar_history_fetcher.cache_calendars")
    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("backend.historical_data.google_calendar_history_fetcher.cache_events")
    def test_pull_calendar_history_empty_calendar_keys(
        self,
        mock_cache_events,
        mock_redis_factory,
        mock_cache_calendars,
        mock_get_ldaps,
    ):
        mock_redis = MagicMock()
        mock_redis.hkeys.return_value = []
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis
        mock_get_ldaps.return_value = ["user1"]
        mock_cache_events.return_value = set()

        pull_calendar_history()

        self.assertEqual(mock_cache_events.call_count, 1)  # Only personal calendars
        mock_get_ldaps.assert_called_once()

    @patch(
        "backend.historical_data.google_calendar_history_fetcher.get_all_active_ldap_users"
    )
    @patch("backend.historical_data.google_calendar_history_fetcher.cache_calendars")
    @patch("backend.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("backend.historical_data.google_calendar_history_fetcher.cache_events")
    def test_pull_calendar_history_retries_then_succeeds(
        self,
        mock_cache_events,
        mock_redis_factory,
        mock_cache_calendars,
        mock_get_ldaps,
    ):
        cache_attempts = [Exception("fail 1"), Exception("fail 2"), None]

        def cache_calendars_side_effect():
            result = cache_attempts.pop(0)
            if result:
                raise result

        mock_cache_calendars.side_effect = cache_calendars_side_effect
        mock_redis = MagicMock()
        mock_redis.hkeys.return_value = ["team@group.v.calendar.google.com"]
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis
        mock_cache_events.return_value = {"event1"}
        mock_get_ldaps.return_value = ["user1"]

        pull_calendar_history()

        self.assertEqual(mock_cache_calendars.call_count, 3)
        self.assertEqual(mock_cache_events.call_count, 2)

    @patch("backend.historical_data.google_calendar_history_fetcher.cache_calendars")
    def test_pull_calendar_history_retries_then_fails(
        self,
        mock_cache_calendars,
    ):
        mock_cache_calendars.side_effect = Exception("always failing")

        with self.assertRaises(Exception):
            pull_calendar_history()

        self.assertEqual(mock_cache_calendars.call_count, 3)


if __name__ == "__main__":
    main()
