from unittest import TestCase, main
from unittest.mock import patch, MagicMock, ANY
from src.historical_data.google_calendar_history_fetcher import (
    get_calendar_list,
    get_calendar_events,
    get_event_attendance,
    get_meeting_code_from_event,
    cache_calendars,
    cache_events,
)
from googleapiclient.errors import HttpError

MOCK_CALENDAR_LIST_PAGE_1 = {
    "items": [
        {
            "id": "cal1",
            "summary": "Work",
            "description": "Work calendar",
            "timeZone": "America/New_York",
        },
        {
            "id": "cal2",
            "summary": "Personal",
            "description": "Personal calendar",
            "timeZone": "America/Los_Angeles",
        },
    ],
    "nextPageToken": "token123",
}

MOCK_CALENDAR_LIST_PAGE_2 = {
    "items": [
        {
            "id": "cal3",
            "summary": "School",
            "description": "School calendar",
            "timeZone": "Asia/Taipei",
        }
    ]
}

MOCK_EVENTS_PAGE_1 = {
    "items": [
        {
            "id": "event1",
            "summary": "Engineering Sync",
            "description": "Weekly team sync",
            "start": {"dateTime": "2025-06-13T10:00:00Z"},
            "end": {"dateTime": "2025-06-13T11:00:00Z"},
            "organizer": {"email": "host@circlecat.org"},
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
            "description": "1:1 discussion",
            "start": {"dateTime": "2025-06-13T12:00:00Z"},
            "end": {"dateTime": "2025-06-13T12:30:00Z"},
            "organizer": {"email": "manager@circlecat.org"},
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
            "description": "Monthly update",
            "start": {"dateTime": "2025-06-13T14:00:00Z"},
            "end": {"dateTime": "2025-06-13T15:00:00Z"},
            "organizer": {"email": "ceo@circlecat.org"},
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
                    "actor": {"email": "user1@example.com"},
                    "type": "call_ended",
                    "parameters": [
                        {"name": "duration_seconds", "intValue": "120"},
                        {"name": "start_timestamp_seconds", "intValue": "1716712800"},
                        {"name": "identifier", "value": "user1@example.com"},
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

MOCK_EVENT_RETURN_VALUE = {
    "event_id": "evt123",
    "calendar_id": "team@circlecat.org",
    "title": "Meeting",
    "start": "2024-06-17T10:00:00",
    "end": "2024-06-17T11:00:00",
    "attendees": [{"email": "alice@circlecat.org"}],
    "is_recurring": False,
    "organizer": "org@circlecat.org",
}


class TestGetCalendarList(TestCase):
    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory")
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
                "description": "Work calendar",
                "timeZone": "America/New_York",
            },
            {
                "calendar_id": "cal2",
                "summary": "Personal",
                "description": "Personal calendar",
                "timeZone": "America/Los_Angeles",
            },
            {
                "calendar_id": "cal3",
                "summary": "School",
                "description": "School calendar",
                "timeZone": "Asia/Taipei",
            },
        ]
        self.assertEqual(calendars, expected)

        self.assertEqual(mock_calendar_list.list.call_count, 2)
        mock_factory.create_calendar_client.assert_called_once()

    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory")
    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    def test_get_calendar_list_general_exception(self, mock_logger, mock_factory_class):
        mock_factory = MagicMock()
        mock_factory.create_calendar_client.side_effect = Exception("Failed to connect")
        mock_factory_class.return_value = mock_factory

        calendars = get_calendar_list()

        self.assertEqual(calendars, [])
        mock_logger.error.assert_called_with("Unexpected error fetching calendars", ANY)

    @patch("src.historical_data.google_calendar_history_fetcher.get_event_attendance")
    @patch(
        "src.historical_data.google_calendar_history_fetcher.get_meeting_code_from_event"
    )
    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory")
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
                "title": "Engineering Sync",
                "description": "Weekly team sync",
                "start": "2025-06-13T10:00:00Z",
                "end": "2025-06-13T11:00:00Z",
                "attendees": {"attendee_summary": "Present"},
                "is_recurring": False,
                "organizer": "host@circlecat.org",
            },
            {
                "event_id": "event2",
                "calendar_id": "test-calendar",
                "title": "One-on-One",
                "description": "1:1 discussion",
                "start": "2025-06-13T12:00:00Z",
                "end": "2025-06-13T12:30:00Z",
                "attendees": {"attendee_summary": "Present"},
                "is_recurring": False,
                "organizer": "manager@circlecat.org",
            },
            {
                "event_id": "event3",
                "calendar_id": "test-calendar",
                "title": "Company All-Hands",
                "description": "Monthly update",
                "start": "2025-06-13T14:00:00Z",
                "end": "2025-06-13T15:00:00Z",
                "attendees": {"attendee_summary": "Present"},
                "is_recurring": False,
                "organizer": "ceo@circlecat.org",
            },
        ]
        self.assertEqual(events, expected)
        self.assertEqual(mock_events.list.call_count, 2)

    @patch(
        "src.historical_data.google_calendar_history_fetcher.GoogleClientFactory",
        side_effect=Exception("Simulated API Failure"),
    )
    def test_get_calendar_events_exception(self, mock_factory):
        calendar_id = "dummy_calendar_id"
        time_min = "2023-01-01T00:00:00Z"
        time_max = "2023-01-31T23:59:59Z"

        with self.assertRaises(Exception) as context:
            get_calendar_events(calendar_id, time_min, time_max)

        self.assertEqual(str(context.exception), "Simulated API Failure")

    @patch("src.historical_data.google_calendar_history_fetcher.get_event_attendance")
    @patch(
        "src.historical_data.google_calendar_history_fetcher.get_meeting_code_from_event"
    )
    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory")
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

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory")
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
        self.assertEqual(attendance[0]["email"], "user1@example.com")
        self.assertEqual(attendance[0]["duration_seconds"], 120)
        self.assertTrue(
            attendance[0]["join_time"].endswith("Z")
            or "T" in attendance[0]["join_time"]
        )
        self.assertTrue(
            attendance[0]["leave_time"].endswith("Z")
            or "T" in attendance[0]["leave_time"]
        )

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory")
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

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory")
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
        self.assertEqual(attendance[0]["email"], "user1@example.com")
        self.assertEqual(mock_list.execute.call_count, 2)

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    def test_get_meeting_code_from_event_success(self, mock_logger):
        code = get_meeting_code_from_event(MOCK_EVENT)
        self.assertEqual(code, "abcdefghi")

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    def test_get_meeting_code_from_event_no_uri(self, mock_logger):
        event = {"conferenceData": {"entryPoints": []}}
        code = get_meeting_code_from_event(event)
        self.assertIsNone(code)
        mock_logger.warning.assert_called()

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    def test_get_meeting_code_from_event_exception(self, mock_logger):
        event = None
        code = get_meeting_code_from_event(event)
        self.assertIsNone(code)
        mock_logger.exception.assert_called()

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    @patch("src.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_list")
    def test_cache_calendars_success(
        self,
        mock_get_calendar_list,
        mock_validate_data,
        mock_redis_factory,
        mock_logger,
    ):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        mock_get_calendar_list.return_value = [
            {
                "calendar_id": "work_calendar@group.calendar.google.com",
                "summary": "Work Calendar",
            },
            {"calendar_id": "user@circlecat.org", "summary": "user's Calendar"},  # ldap
        ]

        cache_calendars()

        assert mock_validate_data.call_count == 1
        mock_pipeline.sadd.assert_called_once()
        mock_pipeline.zadd.assert_called_once()
        mock_pipeline.set.assert_called_once()
        mock_pipeline.execute.assert_called_once()

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    @patch("src.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_list")
    def test_cache_calendars_no_ldap_found(
        self,
        mock_get_calendar_list,
        mock_validate_data,
        mock_redis_factory,
        mock_logger,
    ):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        mock_get_calendar_list.return_value = [
            {"calendar_id": "work_calendar@group.calendar.google.com"},
            {"calendar_id": "other@group.v.calendar.google.com"},
            {"calendar_id": "personal"},
        ]

        cache_calendars()

        mock_logger.warning.assert_called_with(
            "No calendar_id ending with @circlecat.org found; skipping caching."
        )
        mock_pipeline.zadd.assert_not_called()
        mock_pipeline.sadd.assert_not_called()
        mock_pipeline.set.assert_not_called()
        mock_pipeline.execute.assert_not_called()

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    @patch("src.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_list")
    def test_cache_calendars_invalid_calendar_skipped(
        self,
        mock_get_calendar_list,
        mock_validate_data,
        mock_redis_factory,
        mock_logger,
    ):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        mock_get_calendar_list.return_value = [
            {"calendar_id": "work_calendar@group.calendar.google.com"},
            {"calendar_id": "user@circlecat.org"},
        ]
        mock_validate_data.side_effect = Exception("invalid schema")

        cache_calendars()

        mock_logger.warning.assert_called_once()
        mock_pipeline.set.assert_not_called()
        mock_pipeline.zadd.assert_not_called()
        mock_pipeline.sadd.assert_not_called()
        mock_pipeline.execute.assert_not_called()

    @patch("src.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_list")
    @patch("src.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    def test_cache_calendars_retries_then_succeeds(
        self, mock_factory, mock_get_calendar_list, mock_validate_data
    ):
        mock_get_calendar_list.side_effect = [
            Exception("Temporary error"),
            Exception("Temporary error"),
            [
                {"calendar_id": "work_calendar@group.calendar.google.com"},
                {"calendar_id": "user@circlecat.org"},
            ],
        ]

        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_factory.return_value.create_redis_client.return_value = mock_redis

        cache_calendars()

        self.assertEqual(mock_get_calendar_list.call_count, 3)

        self.assertTrue(mock_pipeline.zadd.called)
        self.assertTrue(mock_pipeline.set.called)
        mock_pipeline.execute.assert_called_once()

    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_list")
    def test_cache_calendars_retries_3_times_and_fails(self, mock_get_calendar_list):
        mock_get_calendar_list.side_effect = Exception("API error")

        with self.assertRaises(Exception):
            cache_calendars()

        self.assertEqual(mock_get_calendar_list.call_count, 3)

    @patch("src.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_events")
    def test_cache_events_success(
        self,
        mock_get_calendar_events,
        mock_validate_data,
        mock_redis_factory
    ):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        mock_get_calendar_events.return_value = [MOCK_EVENT_RETURN_VALUE]

        cache_events(
            "team@circlecat.org", "2025-06-01T00:00:00Z", "2025-06-30T23:59:59Z"
        )

        mock_redis.pipeline.assert_called_once()
        mock_pipeline.zadd.assert_any_call(f"user:alice:events", {"evt123": ANY})
        mock_pipeline.set.assert_called_once()
        mock_pipeline.execute.assert_called_once()

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    @patch("src.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_events")
    def test_cache_events_no_circlecat_attendee(
        self, mock_get_events, mock_validate, mock_factory, mock_logger
    ):
        mock_get_events.return_value = [
            {
                "event_id": "evt456",
                "calendar_id": "team@circlecat.org",
                "title": "Private",
                "start": "2024-06-17T14:00:00",
                "end": "2024-06-17T15:00:00",
                "attendees": [{"email": "bob@gmail.com"}],
                "is_recurring": False,
                "organizer": "bob@gmail.com",
            }
        ]

        cache_events(
            "team@circlecat.org", "2024-06-01T00:00:00Z", "2024-06-30T00:00:00Z"
        )

        mock_logger.warning.assert_any_call(
            "No @circlecat.org attendee found for event evt456; skipping."
        )

    @patch("src.historical_data.google_calendar_history_fetcher.logger")
    @patch("src.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_events")
    def test_cache_events_invalid_event_skipped(
        self,
        mock_get_calendar_events,
        mock_validate_data,
        mock_redis_factory,
        mock_logger,
    ):
        mock_redis = MagicMock()
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        mock_get_calendar_events.return_value = [MOCK_EVENT_RETURN_VALUE]
        mock_validate_data.side_effect = Exception("invalid schema")

        cache_events(
            "alice@circlecat.org", "2025-06-01T00:00:00Z", "2025-06-30T23:59:59Z"
        )

        mock_logger.warning.assert_called_once()
        mock_redis.set.assert_not_called()
        mock_redis.zadd.assert_not_called()

    @patch("src.historical_data.google_calendar_history_fetcher.RedisClientFactory")
    @patch("src.historical_data.google_calendar_history_fetcher.validate_data")
    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_events")
    def test_cache_events_retries_then_succeeds(
        self,
        mock_get_calendar_events,
        mock_validate_data,
        mock_redis_factory,
    ):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        mock_get_calendar_events.side_effect = [
            Exception("Temporary error"),
            Exception("Temporary error"),
            [MOCK_EVENT_RETURN_VALUE],
        ]

        cache_events(
            "team@circlecat.org", "2025-06-01T00:00:00Z", "2025-06-30T23:59:59Z"
        )

        self.assertEqual(mock_get_calendar_events.call_count, 3)
        mock_validate_data.assert_called_once()
        mock_pipeline.execute.assert_called_once()
        self.assertEqual(mock_pipeline.set.call_count, 1)
        self.assertEqual(mock_pipeline.zadd.call_count, 3)

    @patch("src.historical_data.google_calendar_history_fetcher.get_calendar_events")
    def test_cache_events_fetch_failure_retries(self, mock_get_calendar_events):
        mock_get_calendar_events.side_effect = Exception("API failure")

        with self.assertRaises(Exception):
            cache_events(
                "alice@circlecat.org", "2025-06-01T00:00:00Z", "2025-06-30T23:59:59Z"
            )

        self.assertEqual(mock_get_calendar_events.call_count, 3)


if __name__ == "__main__":
    main()
