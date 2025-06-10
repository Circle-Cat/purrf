from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from src.historical_data.google_calendar_history_fetcher import (
    get_calendar_list,
    get_calendar_events,
)

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
    "items": [{"id": "event1"}, {"id": "event2"}],
    "nextPageToken": "token123",
}
MOCK_EVENTS_PAGE_2 = {
    "items": [{"id": "event3"}],
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
        mock_logger.error.assert_called_with("Unexpected error fetching calendars")

    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory")
    def test_get_calendar_events_success(self, mock_factory_class):
        mock_factory = MagicMock()
        mock_service = MagicMock()
        mock_events = mock_service.events.return_value
        mock_events.list.return_value.execute.side_effect = [
            MOCK_EVENTS_PAGE_1,
            MOCK_EVENTS_PAGE_2,
        ]

        mock_factory.create_calendar_client.return_value = mock_service
        mock_factory_class.return_value = mock_factory

        calendar_id = "test-calendar"
        time_min = "2025-05-01T00:00:00Z"
        time_max = "2025-05-10T00:00:00Z"

        events = get_calendar_events(calendar_id, time_min, time_max)

        expected = [{"id": "event1"}, {"id": "event2"}, {"id": "event3"}]
        self.assertEqual(events, expected)
        self.assertEqual(mock_events.list.call_count, 2)

    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory", side_effect=Exception("Simulated API Failure"))
    def test_get_calendar_events_exception(self, mock_factory):
        calendar_id = "dummy_calendar_id"
        time_min = "2023-01-01T00:00:00Z"
        time_max = "2023-01-31T23:59:59Z"

        with self.assertRaises(Exception) as context:
            get_calendar_events(calendar_id, time_min, time_max)

        self.assertEqual(str(context.exception), "Simulated API Failure")

    @patch("src.historical_data.google_calendar_history_fetcher.GoogleClientFactory")
    def test_get_calendar_events_retries_on_failure_then_succeeds(self, mock_factory_class):
        mock_factory = MagicMock()
        mock_service = MagicMock()
        mock_events = mock_service.events.return_value

        mock_events.list.return_value.execute.side_effect = [
            Exception("Temporary API failure"),
            {"items": [{"id": "recovered_event"}], "nextPageToken": None},
        ]

        mock_factory.create_calendar_client.return_value = mock_service
        mock_factory_class.return_value = mock_factory

        calendar_id = "retry-calendar"
        time_min = "2025-05-01T00:00:00Z"
        time_max = "2025-05-10T00:00:00Z"

        events = get_calendar_events(calendar_id, time_min, time_max)

        self.assertEqual(events, [{"id": "recovered_event"}])
        self.assertEqual(mock_events.list.return_value.execute.call_count, 2)


if __name__ == "__main__":
    main()
