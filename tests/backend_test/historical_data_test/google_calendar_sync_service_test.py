from unittest import TestCase, main
from unittest.mock import MagicMock, ANY
from datetime import datetime
from backend.historical_data.google_calendar_sync_service import (
    GoogleCalendarSyncService,
)
import json


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
        self.service._is_circlecat_email = lambda email: email.endswith(
            "@circlecat.org"
        )

        self.event_start_time = "2025-11-19T08:00:00"
        self.time_min = "2025-11-01T00:00:00"
        self.time_max = "2025-11-30T23:59:59"
        self.sample_calendar_list = [
            {"calendar_id": "team_calendar1", "summary": "Team Calendar 1"},
            {"calendar_id": "alice@circlecat.org", "summary": "Alice Personal"},
            {
                "calendar_id": "system@group.v.calendar.google.com",
                "summary": "System Calendar",
            },
            {"calendar_id": "team_calendar2", "summary": "Team Calendar 2"},
        ]
        self.sample_events_dict = {
            "event1_123": {
                "calendar_id": "calendar1",
                "summary": "Event 1",
                "start": self.event_start_time,
                "is_recurring": False,
                "meeting_code": "event1",
            },
            "event2_456": {
                "calendar_id": "calendar2",
                "summary": "Event 2",
                "start": "2025-11-19T09:00:00",
                "is_recurring": True,
                "meeting_code": "event2",
            },
        }
        self.sample_attendance = {
            "event1_123": [
                {
                    "ldap": "alice",
                    "join_time": "2025-11-19T08:00:00Z",
                    "leave_time": "2025-11-19T09:00:00Z",
                }
            ]
        }
        self.sample_ldap_dict = {"alice": "alice", "bob": "bob"}

    def test_get_meeting_code_from_event_success(self):
        event = {
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/abc-def-ghi",
                    }
                ]
            }
        }

        code = self.service._get_meeting_code_from_event(event)
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

    def test_get_calendar_list_single_page(self):
        mock_response = {
            "items": [
                {"id": "calendar1", "summary": "Calendar 1"},
                {"id": "calendar2", "summary": "Calendar 2"},
            ]
        }
        self.mock_google_calendar_client.calendarList.return_value.list.return_value.execute.return_value = mock_response

        calendars = self.service._get_calendar_list()

        self.assertEqual(len(calendars), 2)
        self.assertEqual(calendars[0]["calendar_id"], "calendar1")
        self.assertEqual(calendars[1]["summary"], "Calendar 2")

    def test_get_calendar_list_multiple_pages(self):
        responses = [
            {
                "items": [{"id": "calendar1", "summary": "Calendar 1"}],
                "nextPageToken": "token1",
            },
            {"items": [{"id": "calendar2", "summary": "Calendar 2"}]},
        ]

        def execute_side_effect(*args, **kwargs):
            return responses.pop(0)

        self.mock_google_calendar_client.calendarList.return_value.list.return_value.execute.side_effect = execute_side_effect

        calendars = self.service._get_calendar_list()

        self.assertEqual(len(calendars), 2)
        self.assertEqual(calendars[0]["calendar_id"], "calendar1")
        self.assertEqual(calendars[1]["calendar_id"], "calendar2")

    def test_get_calendar_list_api_exception(self):
        self.mock_google_calendar_client.calendarList.return_value.list.return_value.execute.side_effect = Exception(
            "API error"
        )

        calendars = self.service._get_calendar_list()

        self.assertEqual(calendars, [])
        self.mock_logger.error.assert_called_with(
            "Unexpected error fetching calendars", ANY
        )

    def test_get_calendars_events_success(self):
        sample_event = {
            "id": "event1",
            "summary": "Event 1",
            "start": {"dateTime": "2025-11-01T10:00:00"},
        }

        def new_batch_http_request_side_effect(callback):
            mock_batch = MagicMock()
            mock_batch._callback = callback

            def execute_side_effect():
                for call_args in mock_batch.add.call_args_list:
                    request_id = call_args[1]["request_id"]
                    callback(request_id, {"items": [sample_event]}, None)

            mock_batch.execute.side_effect = execute_side_effect
            return mock_batch

        self.mock_google_calendar_client.new_batch_http_request.side_effect = (
            new_batch_http_request_side_effect
        )

        mock_req = MagicMock()
        self.mock_google_calendar_client.events.return_value.list.return_value = (
            mock_req
        )

        self.service._get_meeting_code_from_event = lambda e: "event1"

        events_dict = self.service._get_calendars_events(
            ["calendar1"], "2025-11-01T00:00:00Z", "2025-11-02T00:00:00Z"
        )

        self.assertIn("event1", events_dict)
        self.assertEqual(events_dict["event1"]["meeting_code"], "event1")
        self.mock_google_calendar_client.new_batch_http_request.assert_called()

    def test_get_calendars_events_no_meeting_code(self):
        mock_batch = MagicMock()
        self.mock_google_calendar_client.new_batch_http_request.return_value = (
            mock_batch
        )
        mock_req = MagicMock()
        self.mock_google_calendar_client.events.return_value.list.return_value = (
            mock_req
        )
        mock_req.execute.return_value = {
            "items": [
                {
                    "id": "event1",
                    "summary": "Event 1",
                    "start": {"dateTime": "2025-11-01T10:00:00"},
                },
                {
                    "id": "event2",
                    "summary": "Event 2",
                    "start": {"dateTime": "2025-11-02T10:00:00"},
                },
            ]
        }

        self.service._get_meeting_code_from_event = lambda e: None

        events_dict = self.service._get_calendars_events(
            ["calendar1", "calendar2"], "2025-11-01T00:00:00Z", "2025-11-03T00:00:00Z"
        )

        self.assertEqual(events_dict, {})

    def test_get_calendars_events_exception_in_batch_add(self):
        mock_batch = MagicMock()
        mock_batch.add.side_effect = Exception("Add failed")
        self.mock_google_calendar_client.new_batch_http_request.return_value = (
            mock_batch
        )
        mock_req = MagicMock()
        self.mock_google_calendar_client.events.return_value.list.return_value = (
            mock_req
        )
        mock_req.execute.return_value = {
            "items": [
                {
                    "id": "event1",
                    "summary": "Event 1",
                    "start": {"dateTime": "2025-11-01T10:00:00"},
                }
            ]
        }

        self.service._get_meeting_code_from_event = lambda e: "event1"

        self.service._get_calendars_events(
            ["calendar1"], "2025-11-01T00:00:00Z", "2025-11-02T00:00:00Z"
        )

        found_warning = any(
            "Add failed" in str(call.args)
            for call in self.mock_logger.warning.call_args_list
        )
        self.assertTrue(found_warning)

    def test_get_event_attendees_success(self):
        sample_events = {
            "event1": {
                "calendar_ids": ["calendar1"],
                "summary": "Event 1",
                "start": "2025-11-01T10:00:00",
                "is_recurring": False,
                "meeting_code": "event1",
            }
        }

        sample_response = {
            "items": [
                {
                    "events": [
                        {
                            "actor": {"email": "alice@circlecat.org"},
                            "parameters": [
                                {
                                    "name": "start_timestamp_seconds",
                                    "intValue": 1700000000,
                                },
                                {"name": "duration_seconds", "intValue": 3600},
                            ],
                        }
                    ]
                }
            ]
        }

        def new_batch_http_request_side_effect(callback):
            mock_batch = MagicMock()
            mock_batch._callback = callback

            def execute_side_effect():
                for call_args in mock_batch.add.call_args_list:
                    request_id = call_args[1]["request_id"]
                    callback(request_id, sample_response, None)

            mock_batch.execute.side_effect = execute_side_effect
            return mock_batch

        self.mock_google_reports_client.new_batch_http_request.side_effect = (
            new_batch_http_request_side_effect
        )
        mock_req = MagicMock()
        self.mock_google_reports_client.activities.return_value.list.return_value = (
            mock_req
        )

        result = self.service._get_events_attendees(sample_events)

        self.assertIn("event1", result)
        self.assertEqual(len(result["event1"]), 1)
        self.assertEqual(result["event1"][0]["ldap"], "alice")

    def test_get_event_attendees_retries(self):
        sample_events = {
            "event1": {
                "calendar_ids": ["calendar1"],
                "summary": "Event 1",
                "start": "2025-11-01T10:00:00",
                "is_recurring": False,
                "meeting_code": "event1",
            }
        }

        sample_response = {
            "items": [
                {
                    "events": [
                        {
                            "actor": {"email": "bob@circlecat.org"},
                            "parameters": [
                                {
                                    "name": "start_timestamp_seconds",
                                    "intValue": 1700003600,
                                },
                                {"name": "duration_seconds", "intValue": 1800},
                            ],
                        }
                    ]
                }
            ]
        }

        def new_batch_http_request_side_effect(callback):
            mock_batch = MagicMock()
            mock_batch._callback = callback

            def execute_side_effect():
                for call_args in mock_batch.add.call_args_list:
                    request_id = call_args[1]["request_id"]
                    callback(request_id, sample_response, None)

            mock_batch.execute.side_effect = execute_side_effect
            return mock_batch

        self.mock_google_reports_client.new_batch_http_request.side_effect = (
            new_batch_http_request_side_effect
        )
        self.mock_retry_utils.get_retry_on_transient.side_effect = (
            lambda func, *args, **kwargs: func()
        )
        mock_req = MagicMock()
        self.mock_google_reports_client.activities.return_value.list.return_value = (
            mock_req
        )

        result = self.service._get_events_attendees(sample_events)

        self.assertIn("event1", result)
        self.assertEqual(result["event1"][0]["ldap"], "bob")

    def test_get_event_attendees_exception(self):
        sample_events = {
            "event1": {
                "calendar_ids": ["calendar1"],
                "summary": "Event 1",
                "start": "2025-11-01T10:00:00",
                "is_recurring": False,
                "meeting_code": "event1",
            }
        }

        def new_batch_http_request_side_effect(callback):
            mock_batch = MagicMock()
            mock_batch._callback = callback

            def execute_side_effect():
                for call_args in mock_batch.add.call_args_list:
                    request_id = call_args[1]["request_id"]
                    callback(request_id, None, Exception("API failed"))

            mock_batch.execute.side_effect = execute_side_effect
            return mock_batch

        self.mock_google_reports_client.new_batch_http_request.side_effect = (
            new_batch_http_request_side_effect
        )
        mock_req = MagicMock()
        self.mock_google_reports_client.activities.return_value.list.return_value = (
            mock_req
        )

        result = self.service._get_events_attendees(sample_events)

        self.assertIn("event1", result)
        self.assertEqual(result["event1"], [])
        self.mock_logger.warning.assert_called_with(
            "Failed to fetch attendance for meeting event1: API failed"
        )

    def test_cache_calendars_success(self):
        self.service._get_calendar_list = MagicMock(
            return_value=self.sample_calendar_list
        )
        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        cached_ids = self.service._cache_calendars()

        mock_pipeline.hset.assert_any_call(
            "calendarlist", "personal", "Personal Calendars"
        )
        mock_pipeline.hset.assert_any_call(
            "calendarlist", "team_calendar1", "Team Calendar 1"
        )
        mock_pipeline.hset.assert_any_call(
            "calendarlist", "team_calendar2", "Team Calendar 2"
        )
        self.assertEqual(cached_ids, ["team_calendar1", "team_calendar2"])
        self.mock_retry_utils.get_retry_on_transient.assert_called_with(
            mock_pipeline.execute
        )

    def test_cache_calendars_retries(self):
        """Test that _cache_calendars retries Redis execution on transient errors."""
        self.service._get_calendar_list = MagicMock(
            return_value=[
                {"calendar_id": "team_calendar1", "summary": "Team Calendar 1"},
            ]
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        def execute_side_effect():
            return "ok"

        mock_pipeline.execute.side_effect = execute_side_effect

        cached_ids = self.service._cache_calendars()

        self.mock_retry_utils.get_retry_on_transient.assert_called_with(
            mock_pipeline.execute
        )
        self.assertEqual(cached_ids, ["team_calendar1"])

    def test_cache_calendars_exception(self):
        """Test that _cache_calendars handles invalid calendars and logs a warning."""
        self.service._get_calendar_list = MagicMock(
            return_value=[
                {"calendar_id": "team_calendar1", "summary": "Team Calendar 1"},
                {"calendar_id": "invalid_calendar", "summary": "Invalid Calendar"},
            ]
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        def validate_data_side_effect(data, schema):
            if data["calendar_id"] == "invalid_calendar":
                raise Exception("Invalid schema")

        self.service.json_schema_validator.validate_data.side_effect = (
            validate_data_side_effect
        )

        cached_ids = self.service._cache_calendars()

        self.assertEqual(cached_ids, ["team_calendar1"])
        self.mock_logger.warning.assert_called_with(
            "Invalid calendar skipped: Invalid schema"
        )

    def test_cache_calendar_events_success(self):
        self.service._get_calendars_events = MagicMock(
            return_value=self.sample_events_dict
        )
        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        events_dict = self.service._cache_calendar_events(
            calendar_ids=["calendar1", "calendar2", "alice@circlecat.org"],
            time_min=self.time_min,
            time_max=self.time_max,
        )

        mock_pipeline.set.assert_any_call(
            "event:event1",
            json.dumps({
                "summary": "Event 1",
                "calendar_id": "calendar1",
                "is_recurring": False,
            }),
        )
        mock_pipeline.set.assert_any_call(
            "event:event2",
            json.dumps({
                "summary": "Event 2",
                "calendar_id": "calendar2",
                "is_recurring": True,
            }),
        )
        self.assertEqual(set(events_dict.keys()), set(self.sample_events_dict.keys()))
        self.mock_retry_utils.get_retry_on_transient.assert_called_with(
            mock_pipeline.execute
        )

    def test_cache_calendar_events_validation_exception(self):
        self.service._get_calendars_events = MagicMock(
            return_value={
                "event1_123": {
                    "calendar_ids": ["calendar1"],
                    "summary": "Event 1",
                    "start": "2025-11-19T08:00:00",
                    "is_recurring": False,
                    "meeting_code": "event1",
                },
                "event_invalid": {
                    "calendar_ids": ["calendar2"],
                    "summary": "Invalid Event",
                    "start": "2025-11-19T09:00:00",
                    "is_recurring": True,
                    "meeting_code": "invalid",
                },
            }
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        def validate_data_side_effect(data, schema):
            if data["meeting_code"] == "invalid":
                raise Exception("Invalid schema")

        self.service.json_schema_validator.validate_data.side_effect = (
            validate_data_side_effect
        )

        events_dict = self.service._cache_calendar_events(
            calendar_ids=["calendar1", "calendar2"],
            time_min="2025-11-19T00:00:00",
            time_max="2025-11-20T00:00:00",
        )

        mock_pipeline.set.assert_any_call("event:event1", ANY)
        self.assertNotIn("event_invalid", events_dict)
        self.mock_logger.warning.assert_called_with(
            "Invalid event skipped: Invalid schema"
        )

    def test_cache_calendar_events_retry_on_execute(self):
        self.service._get_calendars_events = MagicMock(
            return_value={
                "event1_123": {
                    "calendar_ids": ["calendar1"],
                    "summary": "Event 1",
                    "start": "2025-11-19T08:00:00",
                    "is_recurring": False,
                    "meeting_code": "event1",
                }
            }
        )

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        self.service._cache_calendar_events(
            calendar_ids=["calendar1"],
            time_min="2025-11-19T00:00:00",
            time_max="2025-11-20T00:00:00",
        )

        self.mock_retry_utils.get_retry_on_transient.assert_called_with(
            mock_pipeline.execute
        )

    def test_cache_events_attendees_success(self):
        self.service._get_events_attendees = MagicMock(
            return_value=self.sample_attendance
        )
        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        self.service._cache_events_attendees(
            self.sample_events_dict, time_min=self.time_min, time_max=self.time_max
        )

        record_str = json.dumps({
            "join_time": "2025-11-19T08:00:00Z",
            "leave_time": "2025-11-19T09:00:00Z",
        })
        mock_pipeline.sadd.assert_called_with(
            "event:event1_123:user:alice:attendance", record_str
        )
        score = int(datetime.fromisoformat(self.event_start_time).timestamp())
        mock_pipeline.zadd.assert_any_call(
            "calendar:calendar1:user:alice:events", {"event1_123": score}
        )
        self.mock_retry_utils.get_retry_on_transient.assert_called_with(
            mock_pipeline.execute
        )

    def test_cache_events_attendees_no_attendees(self):
        self.service._get_events_attendees = MagicMock()
        events = {
            "event1": {
                "calendar_id": "calendar1",
                "start": "2025-11-19T08:00:00",
                "meeting_code": "event1",
                "is_recurring": False,
            }
        }
        self.service._get_events_attendees.return_value = {}

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        self.service._cache_events_attendees(events, time_min=None, time_max=None)

        mock_pipeline.sadd.assert_not_called()
        mock_pipeline.zadd.assert_not_called()
        self.mock_retry_utils.get_retry_on_transient.assert_called_with(
            mock_pipeline.execute
        )

    def test_cache_events_attendees_invalid_start(self):
        self.service._get_events_attendees = MagicMock()
        events = {
            "event1": {
                "calendar_id": "calendar1",
                "start": "invalid-time",
                "meeting_code": "event1",
                "is_recurring": False,
            }
        }
        self.service._get_events_attendees.return_value = {
            "event1": [
                {
                    "ldap": "alice",
                    "join_time": "2025-11-19T08:00:00Z",
                    "leave_time": "2025-11-19T09:00:00Z",
                }
            ]
        }

        mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline

        self.service._cache_events_attendees(events, time_min=None, time_max=None)

        mock_pipeline.sadd.assert_not_called()
        mock_pipeline.zadd.assert_not_called()

        self.mock_logger.warning.assert_called_with(ANY)
        self.mock_retry_utils.get_retry_on_transient.assert_called_with(
            mock_pipeline.execute
        )

    def test_pull_calendar_history_success(self):
        self.mock_google_service.list_directory_all_people_ldap.return_value = (
            self.sample_ldap_dict
        )
        self.service._cache_events_attendees = MagicMock()
        self.service._cache_calendars = MagicMock(
            return_value=["calendar1", "calendar2"]
        )
        self.service._cache_calendar_events = MagicMock(
            return_value=self.sample_events_dict
        )

        self.service.pull_calendar_history(
            time_min=self.time_min, time_max=self.time_max
        )

        self.service._cache_calendars.assert_called_once()
        personal_calendar_ids = [
            f"{ldap}@circlecat.org" for ldap in self.sample_ldap_dict.values()
        ]
        expected_all_ids = ["calendar1", "calendar2"] + personal_calendar_ids
        self.service._cache_calendar_events.assert_called_once_with(
            expected_all_ids, self.time_min, self.time_max
        )
        self.service._cache_events_attendees.assert_called_once_with(
            self.sample_events_dict, self.time_min, self.time_max
        )

    def test_pull_calendar_history_no_time(self):
        self.mock_google_service.list_directory_all_people_ldap.return_value = {
            "alice": "alice",
            "bob": "bob",
        }
        self.service._cache_events_attendees = MagicMock()
        self.service._cache_calendars = MagicMock(
            return_value=["calendar1", "calendar2"]
        )
        self.service._cache_calendar_events = MagicMock(
            return_value={
                "event1": {
                    "calendar_id": "calendar1",
                    "summary": "Event 1",
                    "start": "2025-11-19T08:00:00",
                    "is_recurring": False,
                    "meeting_code": "event1",
                }
            }
        )

        self.service.pull_calendar_history()

        self.service._cache_calendars.assert_called_once()
        personal_calendar_ids = ["alice@circlecat.org", "bob@circlecat.org"]
        expected_all_ids = ["calendar1", "calendar2"] + personal_calendar_ids
        self.service._cache_calendar_events.assert_called_once_with(
            expected_all_ids, None, None
        )
        self.service._cache_events_attendees.assert_called_once_with(
            self.service._cache_calendar_events.return_value, None, None
        )


if __name__ == "__main__":
    main()
