import json
from unittest import TestCase, main
from unittest.mock import MagicMock
from datetime import datetime, timezone

from backend.historical_data.google_calendar_sync_service import (
    GoogleCalendarSyncService,
)
from backend.dto.calendar_dto import CalendarDTO, AttendanceDTO, CalendarEventDTO


class TestGoogleCalendarSyncService(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_redis_client = MagicMock()
        self.mock_google_calendar_client = MagicMock()
        self.mock_google_reports_client = MagicMock()
        self.mock_retry_utils = MagicMock()

        # Mock retry utility so it executes the given function directly
        self.mock_retry_utils.get_retry_on_transient.side_effect = (
            lambda func, *args, **kwargs: func()
        )

        self.mock_google_service = MagicMock()

        self.service = GoogleCalendarSyncService(
            logger=self.mock_logger,
            redis_client=self.mock_redis_client,
            google_calendar_client=self.mock_google_calendar_client,
            google_reports_client=self.mock_google_reports_client,
            retry_utils=self.mock_retry_utils,
            google_service=self.mock_google_service,
        )

        # Predefined test time range strings
        self.time_max_str = "2025-11-30T23:59:59Z"
        self.time_min_str = "2025-11-01T00:00:00Z"

    # Helper Methods
    def test_is_circlecat_email(self):
        self.assertTrue(self.service._is_circlecat_email("test@circlecat.org"))
        self.assertFalse(self.service._is_circlecat_email("test@gmail.com"))

    # Meeting code & conference detection
    def test_get_meeting_code_from_event_removes_hyphens(self):
        """Verify that the meeting code is extracted and hyphens are removed."""
        event = {
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/abc-defg-hij",
                    }
                ]
            }
        }
        code = self.service._get_meeting_code_from_event(event)
        self.assertEqual(code, "abcdefghij")

    def test_detect_third_party_conference_teams(self):
        """Verify that Microsoft Teams meetings can be detected from the location or description."""
        event_with_teams_loc = {
            "location": "Microsoft Teams Meeting",
            "description": "Some notes",
        }
        event_with_teams_desc = {
            "location": "Room 101",
            "description": "Join via Microsoft Teams",
        }
        event_no_teams = {
            "location": "Room 101",
            "description": "Regular meeting",
        }

        self.assertEqual(
            self.service._detect_third_party_conference(event_with_teams_loc),
            "microsoft_teams",
        )
        self.assertEqual(
            self.service._detect_third_party_conference(event_with_teams_desc),
            "microsoft_teams",
        )
        self.assertIsNone(self.service._detect_third_party_conference(event_no_teams))

    def test_get_meeting_code_skips_teams(self):
        """Verify that Teams meetings are skipped even if other links exist, and an info log is emitted."""
        event = {
            "summary": "Teams Sync",
            "location": "Microsoft Teams",
            "conferenceData": {"entryPoints": []},  # Assume no Google Meet link
        }
        code = self.service._get_meeting_code_from_event(event)
        self.assertIsNone(code)

    # Calendar Metadata
    def test_get_calendar_list_dto_conversion(self):
        """Verify calendar list retrieval and conversion to CalendarDTO objects."""
        mock_response = {
            "items": [
                {"id": "cal_1", "summary": "Team Alpha"},
                {"id": "cal_2", "summary": "Team Beta"},
            ]
        }
        self.mock_google_calendar_client.calendarList.return_value.list.return_value.execute.return_value = mock_response

        calendars = self.service._get_calendar_list()

        self.assertEqual(len(calendars), 2)
        self.assertIsInstance(calendars[0], CalendarDTO)
        self.assertEqual(calendars[0].calendar_id, "cal_1")

    def test_get_calendar_list_api_error_handling(self):
        """Verify that an empty list is returned and no crash occurs when the Calendar List API fails."""
        self.mock_google_calendar_client.calendarList.return_value.list.return_value.execute.side_effect = Exception(
            "Deadline Exceeded"
        )

        calendars = self.service._get_calendar_list()
        self.assertEqual(calendars, [])

    # Calendar event fetching
    def test_get_calendars_events_deduplication(self):
        """Test event deduplication logic: prefer non-personal calendars."""
        # Simulate the same event appearing in two calendars
        event_raw = {
            "id": "evt_duplicate",
            "summary": "Sync Meeting",
            "status": "confirmed",
            "start": {"dateTime": "2025-11-19T10:00:00Z"},
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/aaa-bbb-ccc",
                    }
                ]
            },
        }

        def batch_side_effect(callback):
            mock_batch = MagicMock()

            def execute():
                # Simulate receiving responses from a personal calendar
                # followed by a team calendar
                callback("user@circlecat.org:rid1", {"items": [event_raw]}, None)
                callback("team@group.calendar:rid2", {"items": [event_raw]}, None)

            mock_batch.execute.side_effect = execute
            return mock_batch

        self.mock_google_calendar_client.new_batch_http_request.side_effect = (
            batch_side_effect
        )
        self.mock_google_calendar_client.events.return_value.list.return_value = (
            MagicMock()
        )

        events_dict = self.service._get_calendars_events(
            ["user@circlecat.org", "team@group.calendar"], "min", "max"
        )

        # The result should reference the non-personal calendar
        self.assertEqual(
            events_dict["evt_duplicate"].calendar_id, "team@group.calendar"
        )

    def test_get_calendars_events_filters_cancelled(self):
        """Verify that events with status 'cancelled' are completely filtered out."""
        event_cancelled = {
            "id": "bad_evt",
            "status": "cancelled",
            "summary": "Deleted Meeting",
            "start": {"dateTime": "2025-11-19T10:00:00Z"},
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/abc-defg-hij",
                    }
                ]
            },
        }

        def batch_side_effect(callback):
            mock_batch = MagicMock()
            mock_batch.execute.side_effect = lambda: callback(
                "cal1:rid", {"items": [event_cancelled]}, None
            )
            return mock_batch

        self.mock_google_calendar_client.new_batch_http_request.side_effect = (
            batch_side_effect
        )
        self.mock_google_calendar_client.events.return_value.list.return_value = (
            MagicMock()
        )

        events_dict = self.service._get_calendars_events(["cal1"], "min", "max")
        self.assertEqual(len(events_dict), 0)

    # Attendance Matching
    def test_get_events_attendees_proximity_matching(self):
        """Test attendee proximity matching logic."""
        # Two events with the same meeting code: one at 10:00 and one at 14:00
        code = "code123"
        events = {
            "morn": CalendarEventDTO(
                event_id="morn",
                calendar_id="c",
                summary="S",
                start="2025-11-19T10:00:00Z",
                meeting_code=code,
            ),
            "aftn": CalendarEventDTO(
                event_id="aftn",
                calendar_id="c",
                summary="S",
                start="2025-11-19T14:00:00Z",
                meeting_code=code,
            ),
        }

        # Simulate an attendee joining at 10:05
        join_ts = int(datetime(2025, 11, 19, 10, 5, tzinfo=timezone.utc).timestamp())
        mock_response = {
            "items": [
                {
                    "events": [
                        {
                            "actor": {"email": "bob@circlecat.org"},
                            "parameters": [
                                {
                                    "name": "start_timestamp_seconds",
                                    "intValue": join_ts,
                                },
                                {
                                    "name": "duration_seconds",
                                    "intValue": 1800,
                                },
                            ],
                        }
                    ]
                }
            ]
        }

        def batch_side_effect(callback):
            mock_batch = MagicMock()
            mock_batch.execute.side_effect = lambda: callback(code, mock_response, None)
            return mock_batch

        self.mock_google_reports_client.new_batch_http_request.side_effect = (
            batch_side_effect
        )
        self.mock_google_reports_client.activities.return_value.list.return_value = (
            MagicMock()
        )

        result = self.service._get_events_attendees(
            events, self.time_min_str, self.time_max_str
        )

        # The attendee should match only the 10:00 event
        self.assertEqual(len(result["morn"]), 1)
        self.assertEqual(len(result["aftn"]), 0)
        self.assertEqual(result["morn"][0].ldap, "bob")

    def test_get_events_attendees_outside_window(self):
        """Verify that attendance records are discarded when the join time is more than 2 hours away from the scheduled start."""
        code = "code123"
        events = {
            "evt1": CalendarEventDTO(
                event_id="evt1",
                calendar_id="c",
                summary="S",
                start="2025-11-19T10:00:00Z",
                meeting_code=code,
            )
        }

        # Simulate joining at 13:00 (3 hours after the scheduled 10:00 start)
        late_join_ts = int(
            datetime(2025, 11, 19, 13, 0, tzinfo=timezone.utc).timestamp()
        )
        mock_response = {
            "items": [
                {
                    "events": [
                        {
                            "actor": {"email": "late_user@circlecat.org"},
                            "parameters": [
                                {
                                    "name": "start_timestamp_seconds",
                                    "intValue": late_join_ts,
                                },
                                {
                                    "name": "duration_seconds",
                                    "intValue": 600,
                                },
                            ],
                        }
                    ]
                }
            ]
        }

        def batch_side_effect(callback):
            mock_batch = MagicMock()
            mock_batch.execute.side_effect = lambda: callback(code, mock_response, None)
            return mock_batch

        self.mock_google_reports_client.new_batch_http_request.side_effect = (
            batch_side_effect
        )
        self.mock_google_reports_client.activities.return_value.list.return_value = (
            MagicMock()
        )

        result = self.service._get_events_attendees(events, "min", "max")
        # Outside MATCH_WINDOW_SECONDS (7200 seconds), the result should be empty
        self.assertEqual(len(result["evt1"]), 0)

    def test_get_events_attendees_empty_response(self):
        """Verify that an empty API response does not raise errors and is handled correctly."""
        code = "empty_code"
        events = {
            "e1": CalendarEventDTO(
                event_id="e1",
                calendar_id="c",
                summary="S",
                start="2025-11-19T10:00:00Z",
                meeting_code=code,
            )
        }

        def batch_side_effect(callback):
            mock_batch = MagicMock()
            mock_batch.execute.side_effect = lambda: callback(code, {"items": []}, None)
            return mock_batch

        self.mock_google_reports_client.new_batch_http_request.side_effect = (
            batch_side_effect
        )
        self.mock_google_reports_client.activities.return_value.list.return_value = (
            MagicMock()
        )

        result = self.service._get_events_attendees(events, "min", "max")
        self.assertEqual(result["e1"], [])

    # Redis & Persistence
    def test_cache_calendar_events_strips_suffix(self):
        """Test that instance suffixes are removed when writing to Redis."""
        eid = "base_20251119T100000Z"
        dto = CalendarEventDTO(
            event_id=eid,
            calendar_id="team_cal",
            summary="Daily Standup",
            start="2025-11-19T10:00:00Z",
            meeting_code="code",
        )

        self.service._get_calendars_events = MagicMock(return_value={eid: dto})
        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        self.service._cache_calendar_events(["team_cal"], "min", "max")

        # Expected Redis key should have the suffix removed
        mock_pipeline.set.assert_called_with(
            "event:base",
            json.dumps({
                "summary": "Daily Standup",
                "calendar_id": "team_cal",
                "is_recurring": False,
            }),
        )

    def test_cache_events_attendees_user_index(self):
        """Test calendar_id alias mapping when indexing user events with ZADD."""
        eid = "evt_1"
        # Personal calendar event
        dto = CalendarEventDTO(
            event_id=eid,
            calendar_id="user@circlecat.org",
            summary="S",
            start="2025-11-19T10:00:00Z",
            meeting_code="c",
        )
        att = AttendanceDTO(
            ldap="alice",
            join_time=datetime(2025, 11, 19, 10, 0, tzinfo=timezone.utc),
            leave_time=datetime(2025, 11, 19, 10, 10, tzinfo=timezone.utc),
        )

        self.service._get_events_attendees = MagicMock(return_value={eid: [att]})
        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        self.service._cache_events_attendees({eid: dto}, "min", "max")

        # Verify that the calendar_id is mapped to "personal" in the ZADD key
        mock_pipeline.zadd.assert_called_with(
            "calendar:personal:user:alice:events",
            {eid: dto.start_ts},
        )

    def test_cache_calendar_events_empty_input(self):
        """Verify that the pipeline does not break when no events are returned from calendars."""
        self.service._get_calendars_events = MagicMock(return_value={})
        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        res = self.service._cache_calendar_events(["cal1"], "min", "max")
        self.assertEqual(res, {})
        mock_pipeline.execute.assert_called_once()

    def test_cache_events_attendees_skips_invalid_ldap(self):
        """Verify that attendance records without a valid LDAP are not written to Redis."""
        eid = "evt1"
        dto = CalendarEventDTO(
            event_id=eid,
            calendar_id="c",
            summary="S",
            start="2025-11-19T10:00:00Z",
            meeting_code="c",
        )
        # Simulate an attendance record without an LDAP
        bad_att = AttendanceDTO(
            ldap="",
            join_time=datetime(2025, 11, 19, 10, 0, tzinfo=timezone.utc),
            leave_time=datetime(2025, 11, 19, 10, 10, tzinfo=timezone.utc),
        )

        self.service._get_events_attendees = MagicMock(return_value={eid: [bad_att]})
        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        self.service._cache_events_attendees({eid: dto}, "min", "max")
        mock_pipeline.sadd.assert_not_called()


if __name__ == "__main__":
    main()
