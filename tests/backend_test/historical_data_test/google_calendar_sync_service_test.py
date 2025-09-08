from unittest import TestCase, main
from unittest.mock import MagicMock, ANY
from backend.historical_data.google_calendar_sync_service import (
    GoogleCalendarSyncService,
)
import json

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


class HttpError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)


class TestGoogleCalendarSyncService(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_redis_client = MagicMock()
        self.mock_google_calendar_client = MagicMock()
        self.mock_google_reports_client = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.mock_retry_utils.get_retry_on_transient.side_effect = (
            lambda func, *args, **kwargs: func()
        )
        self.mock_google_service = MagicMock()
        self.mock_json_schema_validator = MagicMock()
        self.service = GoogleCalendarSyncService(
            logger=self.mock_logger,
            redis_client=self.mock_redis_client,
            google_calendar_client=self.mock_google_calendar_client,
            google_reports_client=self.mock_google_reports_client,
            retry_utils=self.mock_retry_utils,
            google_service=self.mock_google_service,
            json_schema_validator=self.mock_json_schema_validator,
        )

    def test_get_calendar_list_success(self):
        mock_calendar_list = self.mock_google_calendar_client.calendarList.return_value
        mock_calendar_list.list.return_value.execute.side_effect = [
            MOCK_CALENDAR_LIST_PAGE_1,
            MOCK_CALENDAR_LIST_PAGE_2,
        ]

        calendars = self.service._get_calendar_list()

        expected = [
            {"calendar_id": "cal1", "summary": "Work"},
            {"calendar_id": "cal2", "summary": "Personal"},
            {"calendar_id": "cal3", "summary": "School"},
        ]
        self.assertEqual(calendars, expected)

        self.assertEqual(mock_calendar_list.list.call_count, 2)

    def test_get_calendar_list_general_exception(self):
        mock_calendar_list_api = (
            self.mock_google_calendar_client.calendarList.return_value
        )
        mock_calendar_list_api.list.return_value.execute.side_effect = Exception(
            "Failed to connect"
        )

        calendars = self.service._get_calendar_list()

        self.assertEqual(calendars, [])
        self.mock_logger.error.assert_called_with(
            "Unexpected error fetching calendars", ANY
        )

    def test_get_calendar_events_success(self):
        mock_events_api = self.mock_google_calendar_client.events.return_value
        mock_events_api.list.return_value.execute.side_effect = [
            MOCK_EVENTS_PAGE_1,
            MOCK_EVENTS_PAGE_2,
        ]

        self.service._get_meeting_code_from_event = MagicMock(
            side_effect=[
                "abc-defg-hij",
                "xyz-1234-pqr",
                "qrs-tuv-wxy",
            ]
        )
        self.service._get_event_attendance = MagicMock(
            return_value={"attendee_summary": "Present"}
        )

        calendar_id = "test-calendar"
        time_min = "2025-05-01T00:00:00Z"
        time_max = "2025-05-10T00:00:00Z"

        events = self.service._get_calendar_events(calendar_id, time_min, time_max)

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
        self.assertEqual(mock_events_api.list.return_value.execute.call_count, 2)

    def test_get_calendar_events_exception(self):
        self.mock_google_calendar_client.events.return_value.list.return_value.execute.side_effect = Exception(
            "Simulated API Failure"
        )

        calendar_id = "dummy_calendar_id"
        time_min = "2023-01-01T00:00:00Z"
        time_max = "2023-01-31T23:59:59Z"

        with self.assertRaises(Exception) as context:
            self.service._get_calendar_events(calendar_id, time_min, time_max)

        self.assertEqual(str(context.exception), "Simulated API Failure")

    def test_get_calendar_events_retries_on_failure_then_succeeds(self):
        self.service._get_meeting_code_from_event = MagicMock(
            side_effect=[
                "abc-defg-hij",
                "xyz-1234-pqr",
                "qrs-tuv-wxy",
            ]
        )
        self.service._get_event_attendance = MagicMock(
            return_value={"attendee_summary": "Present"}
        )

        pages = [MOCK_EVENTS_PAGE_1, MOCK_EVENTS_PAGE_2]

        def mock_fetch_page(page_token=None):
            return pages.pop(0)

        self.service.google_calendar_client.events.return_value.list.side_effect = (
            lambda **kwargs: MagicMock(
                execute=lambda: mock_fetch_page(kwargs.get("pageToken"))
            )
        )

        calendar_id = "test_calendar"
        start_time = "2023-01-01T00:00:00Z"
        end_time = "2023-01-02T00:00:00Z"
        result = self.service._get_calendar_events(calendar_id, start_time, end_time)

        self.assertEqual(result[0]["event_id"], "event1")
        self.assertEqual(result[1]["event_id"], "event2")
        self.assertEqual(result[2]["event_id"], "event3")

        self.assertTrue(self.mock_retry_utils.get_retry_on_transient.called)

    def test_get_event_attendance_success(self):
        mock_activities = self.mock_google_reports_client.activities.return_value
        mock_list = mock_activities.list.return_value
        mock_list.execute.return_value = MOCK_REPORTS_RESPONSE

        meeting_code = "abcdefghi"
        attendance = self.service._get_event_attendance(meeting_code)

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

    def test_get_event_attendance_error(self):
        mock_activities = self.mock_google_reports_client.activities.return_value
        mock_list = mock_activities.list.return_value
        mock_list.execute.side_effect = HttpError(
            resp=MagicMock(status=500), content=b"Internal Error"
        )

        meeting_code = "errorcode"

        with self.assertRaises(HttpError):
            self.service._get_event_attendance(meeting_code)

        mock_list.execute.assert_called_once()
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_get_event_attendance_retries_then_succeeds(self):
        mock_activities = self.mock_google_reports_client.activities.return_value
        mock_list = mock_activities.list.return_value
        mock_list.execute.return_value = MOCK_REPORTS_RESPONSE

        meeting_code = "retry-meeting"
        attendance = self.service._get_event_attendance(meeting_code)

        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance[0]["email"], "user1@circlecat.org")

        self.assertTrue(self.mock_retry_utils.get_retry_on_transient.called)

    def test_get_meeting_code_from_event_success(self):
        code = self.service._get_meeting_code_from_event(MOCK_EVENT)
        self.assertEqual(code, "abcdefghi")

    def test_get_meeting_code_from_event_no_uri(self):
        event = {"conferenceData": {"entryPoints": []}}
        code = self.service._get_meeting_code_from_event(event)
        self.assertIsNone(code)
        self.mock_logger.warning.assert_called()

    def test_get_meeting_code_from_event_exception(self):
        event = None
        code = self.service._get_meeting_code_from_event(event)
        self.assertIsNone(code)
        self.mock_logger.exception.assert_called()

    def test_cache_calendars_success(self):
        self.service._get_calendar_list = MagicMock(
            return_value=[
                {"calendar_id": "user@circlecat.org", "summary": "Personal"},
                {"calendar_id": "team1@group.v.calendar.google.com", "summary": "Team"},
                {"calendar_id": "team2@circlecat.org", "summary": "Team2"},
                {
                    "calendar_id": "valid-calendar@calendar.google.com",
                    "summary": "Valid",
                },
            ]
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        mock_validate_data = MagicMock()
        self.mock_json_schema_validator.validate_data = mock_validate_data

        self.service._cache_calendars()
        mock_pipeline.hset.assert_any_call(
            "calendarlist", "personal", "Personal Calendars"
        )
        mock_pipeline.hset.assert_any_call(
            "calendarlist", "valid-calendar@calendar.google.com", "Valid"
        )
        self.assertTrue(mock_pipeline.execute.called)
        assert mock_validate_data.call_count == 1

    def test_cache_calendars_no_ldap_found(self):
        self.service._get_calendar_list = MagicMock(
            return_value=[
                {"calendar_id": "team1@group.v.calendar.google.com", "summary": "Team"},
                {"calendar_id": "invalid@calendar.google.com", "summary": "Invalid"},
            ]
        )

        self.service._cache_calendars()

        self.mock_logger.warning.assert_called_with(
            "No calendar_id ending with @circlecat.org found; skipping caching."
        )

    def test_cache_calendars_invalid_calendar_skipped(self):
        self.service._get_calendar_list = MagicMock(
            return_value=[
                {"calendar_id": "user@circlecat.org", "summary": "Personal"},
                {
                    "calendar_id": "invalid-calendar@calendar.google.com",
                    "summary": "Invalid",
                },
            ]
        )
        self.mock_json_schema_validator.validate_data.side_effect = Exception(
            "schema error"
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        self.service._cache_calendars()

        self.mock_logger.warning.assert_any_call(
            "Invalid calendar skipped: schema error"
        )
        mock_pipeline.hset.assert_called_once_with(
            "calendarlist", "personal", "Personal Calendars"
        )
        mock_pipeline.execute.assert_called()

    def test_cache_calendars_retries_then_succeeds(self):
        self.service._get_calendar_list = MagicMock(
            return_value=[
                {"calendar_id": "user@circlecat.org", "summary": "Personal"},
                {"calendar_id": "valid@calendar.google.com", "summary": "Valid"},
            ]
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        self.service._cache_calendars()

        self.assertTrue(mock_pipeline.execute.called)
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_cache_calendars_retries_3_times_and_fails(self):
        self.service._get_calendar_list = MagicMock(
            return_value=[
                {"calendar_id": "user@circlecat.org", "summary": "Personal"},
                {"calendar_id": "valid@calendar.google.com", "summary": "Valid"},
            ]
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        def always_fail(func, *args, **kwargs):
            raise Exception("Redis pipeline failed")

        self.mock_retry_utils.get_retry_on_transient.side_effect = always_fail

        with self.assertRaises(Exception):
            self.service._cache_calendars()

        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_cache_events_success(self):
        self.service._get_calendar_events = MagicMock(
            return_value=[
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
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline
        self.mock_redis_client.exists.return_value = False

        updated_ids = self.service.cache_events(
            "user@circlecat.org", "2025-07-30T00:00:00", "2025-07-31T00:00:00"
        )

        self.assertIn("event123", updated_ids)
        self.assertTrue(mock_pipeline.set.called)
        self.assertTrue(mock_pipeline.zadd.called)
        self.assertTrue(mock_pipeline.sadd.called)
        self.assertTrue(mock_pipeline.execute.called)

    def test_cache_events_invalid_event_skipped(self):
        self.service._get_calendar_events = MagicMock(
            return_value=[
                {
                    "event_id": "event123",
                    "summary": "Bad Event",
                    "start": "2025-07-30T10:00:00",
                    "attendees": [],
                }
            ]
        )
        self.mock_json_schema_validator.validate_data.side_effect = Exception(
            "validation failed"
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline
        self.mock_redis_client.get.return_value = json.dumps([])

        updated_ids = self.service.cache_events(
            "user@circlecat.org", "2025-07-30T00:00:00", "2025-07-31T00:00:00"
        )

        self.assertIn("event123", updated_ids)
        self.mock_logger.warning.assert_any_call(
            "Invalid event skipped: validation failed"
        )
        mock_pipeline.execute.assert_called()

    def test_cache_events_retries_then_succeeds(self):
        self.service._get_calendar_events = MagicMock(
            return_value=[
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
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline
        self.mock_redis_client.get.return_value = json.dumps([])

        result = self.service.cache_events(
            "user@circlecat.org", "2025-07-30T00:00:00", "2025-07-31T00:00:00"
        )

        self.assertIn("event123", result)
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_cache_events_fetch_failure_retries(self):
        self.service._get_calendar_events = MagicMock(
            return_value=[
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
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline
        self.mock_redis_client.get.return_value = json.dumps([])

        self.service.cache_events(
            "alice@circlecat.org", "2025-06-01T00:00:00Z", "2025-06-30T23:59:59Z"
        )

        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            mock_pipeline.execute
        )

    def test_pull_calendar_history_success(self):
        self.mock_redis_client.hkeys.return_value = [
            "team1@group.v.calendar.google.com",
            "team2@group.v.calendar.google.com",
        ]

        self.service._cache_calendars = MagicMock()
        self.service.cache_events = MagicMock(return_value={"event1", "event2"})

        self.mock_google_service.list_directory_all_people_ldap.return_value = {
            "user1": "user1@circlecat.org",
            "user2": "user2@circlecat.org",
        }

        self.service.pull_calendar_history("2025-07-01T00:00:00", "2025-08-01T00:00:00")

        self.assertEqual(self.service.cache_events.call_count, 4)
        self.service._cache_calendars.assert_called_once()
        self.mock_google_service.list_directory_all_people_ldap.assert_called_once()

    def test_pull_calendar_history_empty_calendar_keys(self):
        self.mock_redis_client.hkeys.return_value = []
        self.mock_google_service.list_directory_all_people_ldap.return_value = {
            "user1": "user1@circlecat.org"
        }
        self.service._cache_calendars = MagicMock()
        self.service.cache_events = MagicMock(return_value=set())

        self.service.pull_calendar_history(
            time_min="2025-07-01T00:00:00Z", time_max="2025-08-01T00:00:00Z"
        )

        self.service._cache_calendars.assert_called_once()
        self.assertEqual(self.service.cache_events.call_count, 1)
        self.mock_google_service.list_directory_all_people_ldap.assert_called_once()

    def test_pull_calendar_history_retries_then_succeeds(self):
        self.mock_redis_client.hkeys.return_value = ["personal"]
        self.service._cache_calendars = MagicMock()
        self.service.cache_events = MagicMock(side_effect=[set(), set()])
        self.mock_google_service.list_directory_all_people_ldap = MagicMock(
            return_value={
                "user1": "user1@circlecat.org",
                "user2": "user2@circlecat.org",
            }
        )

        self.service.pull_calendar_history(
            time_min="2025-07-01T00:00:00Z", time_max="2025-08-01T00:00:00Z"
        )

        self.service._cache_calendars.assert_called_once()
        self.assertEqual(
            self.service.cache_events.call_count, 2
        )  # for personal calendar_ids
        self.mock_google_service.list_directory_all_people_ldap.assert_called_once()

    def test_pull_calendar_history_retries_then_fails(self):
        self.mock_redis_client.hkeys.return_value = ["personal"]
        self.service._cache_calendars = MagicMock()
        self.service.cache_events = MagicMock(
            side_effect=Exception("Cache events failed")
        )
        self.mock_google_service.list_directory_all_people_ldap = MagicMock(
            return_value={"user1": "user1@circlecat.org"}
        )

        with self.assertRaises(Exception) as context:
            self.service.pull_calendar_history(
                time_min="2025-07-01T00:00:00Z", time_max="2025-08-01T00:00:00Z"
            )

        self.assertIn("Cache events failed", str(context.exception))
        self.service._cache_calendars.assert_called_once()
        self.assertTrue(self.service.cache_events.called)
        self.mock_google_service.list_directory_all_people_ldap.assert_called_once()


if __name__ == "__main__":
    main()
