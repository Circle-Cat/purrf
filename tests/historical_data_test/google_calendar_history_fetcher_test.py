from unittest import TestCase, main
from unittest.mock import patch, MagicMock, ANY
from src.historical_data.google_calendar_history_fetcher import (
    get_calendar_list,
    get_calendar_events,
    get_event_attendance,
    get_meeting_code_from_event,
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


if __name__ == "__main__":
    main()
