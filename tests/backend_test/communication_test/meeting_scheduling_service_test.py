"""Unit tests for the domain-agnostic Google meeting scheduling service."""

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from backend.common.exceptions import MeetingGoneError
from backend.communication.meeting_scheduling_service import MeetingSchedulingService

# Every call has to name a calendar: this service is domain-agnostic and holds
# no default, so the tests supply one the way a scenario service would.
CALENDAR = "cal-interview"


def _service(**overrides):
    """A service whose collaborators are all mocks, with sane defaults."""
    logger = MagicMock()
    google = MagicMock()
    google.insert_google_meeting.return_value = {
        "id": "evt-1",
        "hangoutLink": "https://meet.google.com/abc-defg-hij",
        "created": "2026-08-01T00:00:00Z",
        "conferenceData": {
            "conferenceId": "abc-defg-hij",
            "entryPoints": [{"entryPointType": "video"}],
        },
    }
    google.get_meet_space_name = AsyncMock(return_value="spaces/xyz")
    google.update_meet_space_type_to_open = AsyncMock()
    google.batch_delete_google_meetings.return_value = (["evt-1"], [])
    google.update_google_meeting.return_value = (
        google.insert_google_meeting.return_value
    )
    emails = MagicMock()
    emails.get_contact_emails_by_user_ids = AsyncMock(
        return_value={1: "ana@example.com", 2: "bob@example.com"}
    )
    kwargs = {
        "logger": logger,
        "google_service": google,
        "user_emails_repository": emails,
    }
    kwargs.update(overrides)
    return MeetingSchedulingService(**kwargs), kwargs


class ResolveAttendeeEmailsTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_one_address_per_user_in_input_order(self):
        service, _ = _service()
        result = await service.resolve_attendee_emails(MagicMock(), [1, 2])
        self.assertEqual(result, ["ana@example.com", "bob@example.com"])

    async def test_skips_a_user_with_no_contact_address_and_warns(self):
        service, kwargs = _service()
        kwargs["user_emails_repository"].get_contact_emails_by_user_ids = AsyncMock(
            return_value={1: "ana@example.com"}
        )
        result = await service.resolve_attendee_emails(MagicMock(), [1, 2])
        self.assertEqual(result, ["ana@example.com"])
        kwargs["logger"].warning.assert_called_once()

    async def test_deduplicates_when_two_user_ids_share_an_address(self):
        service, kwargs = _service()
        kwargs["user_emails_repository"].get_contact_emails_by_user_ids = AsyncMock(
            return_value={1: "ana@example.com", 2: "ana@example.com"}
        )
        result = await service.resolve_attendee_emails(MagicMock(), [1, 2])
        self.assertEqual(result, ["ana@example.com"])


class CalendarContainerTest(unittest.IsolatedAsyncioTestCase):
    """The container is an argument, never state on this service."""

    def test_does_not_hold_a_calendar_id(self):
        """No calendar id may live on this service.

        Storing one would put a scenario decision inside a deliberately
        domain-agnostic transport layer, and would hand its two callers a
        shared default to silently fall back to -- which is the failure mode
        the whole change exists to remove.
        """
        service, _ = _service()
        self.assertEqual(
            [attr for attr in vars(service) if "calendar" in attr.lower()], []
        )

    async def test_schedule_passes_the_calendar_id_through(self):
        """Creates must land on the container the caller names."""
        service, kwargs = _service()
        await service.schedule(
            MagicMock(),
            "S",
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            [1],
            CALENDAR,
        )
        _, call_kwargs = kwargs["google_service"].insert_google_meeting.call_args
        self.assertEqual(call_kwargs["calendar_id"], CALENDAR)

    async def test_update_passes_the_calendar_id_through(self):
        """Reschedules must land on the same container creates went to."""
        service, kwargs = _service()
        await service.update(
            MagicMock(),
            "evt-1",
            datetime(2026, 8, 7, tzinfo=timezone.utc),
            datetime(2026, 8, 7, tzinfo=timezone.utc),
            [1],
            CALENDAR,
        )
        _, call_kwargs = kwargs["google_service"].update_google_meeting.call_args
        self.assertEqual(call_kwargs["calendar_id"], CALENDAR)

    async def test_cancel_passes_the_calendar_id_through(self):
        """Cancellation is the automation-driven path, so it matters most.

        Recruiting cancels interviews on advance / reject / blacklist, and the
        blacklist sweep covers every application at once -- a wrong container
        here deletes in bulk.
        """
        service, kwargs = _service()
        await service.cancel(["evt-1"], CALENDAR)
        kwargs["google_service"].batch_delete_google_meetings.assert_called_once_with(
            event_ids=["evt-1"], calendar_id=CALENDAR
        )

    async def test_each_method_requires_a_calendar_id(self):
        """Omitting the container must fail loudly, not pick a default."""
        service, _ = _service()
        moment = datetime(2026, 8, 5, tzinfo=timezone.utc)
        with self.assertRaises(TypeError):
            await service.schedule(MagicMock(), "S", moment, moment, [1])
        with self.assertRaises(TypeError):
            await service.update(MagicMock(), "evt-1", moment, moment, [1])
        with self.assertRaises(TypeError):
            await service.cancel(["evt-1"])


class ScheduleTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_normalized_event_fields(self):
        service, _ = _service()
        start = datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 5, 21, 45, tzinfo=timezone.utc)
        result = await service.schedule(
            MagicMock(), "Ana/Circle Cat, Behavioral", start, end, [1, 2], CALENDAR
        )
        self.assertEqual(result["google_event_id"], "evt-1")
        self.assertEqual(result["meet_link"], "https://meet.google.com/abc-defg-hij")
        self.assertEqual(result["conference_id"], "abc-defg-hij")
        self.assertEqual(result["entry_points"], [{"entryPointType": "video"}])
        self.assertEqual(result["created"], "2026-08-01T00:00:00Z")

    async def test_passes_summary_times_and_resolved_emails_to_google(self):
        service, kwargs = _service()
        start = datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 5, 21, 45, tzinfo=timezone.utc)
        await service.schedule(MagicMock(), "Summary", start, end, [1, 2], CALENDAR)
        _, call_kwargs = kwargs["google_service"].insert_google_meeting.call_args
        self.assertEqual(call_kwargs["summary"], "Summary")
        self.assertEqual(call_kwargs["start_time"], start)
        self.assertEqual(call_kwargs["end_time"], end)
        self.assertEqual(
            call_kwargs["attendees_emails"], ["ana@example.com", "bob@example.com"]
        )
        # An event id is minted so the insert is idempotent under retry.
        self.assertTrue(call_kwargs["event_id"])
        self.assertTrue(call_kwargs["request_id"])

    async def test_opens_the_meet_space(self):
        service, kwargs = _service()
        await service.schedule(
            MagicMock(),
            "S",
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            [1],
            CALENDAR,
        )
        kwargs["google_service"].get_meet_space_name.assert_awaited_once_with(
            "abc-defg-hij"
        )
        kwargs[
            "google_service"
        ].update_meet_space_type_to_open.assert_awaited_once_with("spaces/xyz")

    async def test_a_failure_to_open_the_meet_space_is_not_fatal(self):
        service, kwargs = _service()
        kwargs["google_service"].get_meet_space_name = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        result = await service.schedule(
            MagicMock(),
            "S",
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            [1],
            CALENDAR,
        )
        self.assertEqual(result["google_event_id"], "evt-1")
        kwargs["logger"].warning.assert_called()

    async def test_a_google_insert_failure_propagates(self):
        service, kwargs = _service()
        kwargs["google_service"].insert_google_meeting.side_effect = RuntimeError("no")
        with self.assertRaises(RuntimeError):
            await service.schedule(
                MagicMock(),
                "S",
                datetime(2026, 8, 5, tzinfo=timezone.utc),
                datetime(2026, 8, 5, tzinfo=timezone.utc),
                [1],
                CALENDAR,
            )

    async def test_skips_meet_space_calls_when_conference_id_is_missing(self):
        service, kwargs = _service()
        kwargs["google_service"].insert_google_meeting.return_value = {
            "id": "evt-1",
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
            "created": "2026-08-01T00:00:00Z",
            "conferenceData": {},
        }
        result = await service.schedule(
            MagicMock(),
            "S",
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            [1],
            CALENDAR,
        )
        self.assertIsNone(result["conference_id"])
        kwargs["google_service"].get_meet_space_name.assert_not_awaited()
        kwargs["google_service"].update_meet_space_type_to_open.assert_not_awaited()

    async def test_skips_meet_space_calls_when_conference_data_is_absent(self):
        service, kwargs = _service()
        kwargs["google_service"].insert_google_meeting.return_value = {
            "id": "evt-1",
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
            "created": "2026-08-01T00:00:00Z",
        }
        result = await service.schedule(
            MagicMock(),
            "S",
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
            [1],
            CALENDAR,
        )
        self.assertIsNone(result["conference_id"])
        kwargs["google_service"].get_meet_space_name.assert_not_awaited()
        kwargs["google_service"].update_meet_space_type_to_open.assert_not_awaited()


class UpdateTest(unittest.IsolatedAsyncioTestCase):
    async def test_passes_resolved_emails_and_returns_normalized_fields(self):
        service, kwargs = _service()
        start = datetime(2026, 8, 7, 21, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 7, 21, 45, tzinfo=timezone.utc)
        result = await service.update(
            MagicMock(), "evt-1", start, end, [1, 2], CALENDAR
        )
        _, call_kwargs = kwargs["google_service"].update_google_meeting.call_args
        self.assertEqual(call_kwargs["event_id"], "evt-1")
        self.assertEqual(call_kwargs["start_time"], start)
        self.assertEqual(call_kwargs["end_time"], end)
        self.assertEqual(
            call_kwargs["attendees_emails"], ["ana@example.com", "bob@example.com"]
        )
        self.assertEqual(result["google_event_id"], "evt-1")

    async def test_does_not_touch_the_meet_space(self):
        # The conference already exists and is already OPEN; re-opening it on
        # every edit would be a wasted pair of API calls.
        service, kwargs = _service()
        await service.update(
            MagicMock(),
            "evt-1",
            datetime(2026, 8, 7, tzinfo=timezone.utc),
            datetime(2026, 8, 7, tzinfo=timezone.utc),
            [1],
            CALENDAR,
        )
        kwargs["google_service"].get_meet_space_name.assert_not_awaited()

    async def test_a_gone_event_propagates(self):
        service, kwargs = _service()
        kwargs["google_service"].update_google_meeting.side_effect = MeetingGoneError(
            "gone"
        )
        with self.assertRaises(MeetingGoneError):
            await service.update(
                MagicMock(),
                "evt-1",
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                [1],
                CALENDAR,
            )


class CancelTest(unittest.IsolatedAsyncioTestCase):
    async def test_delegates_to_the_batch_delete(self):
        service, kwargs = _service()
        succeeded, failed = await service.cancel(["evt-1", "evt-2"], CALENDAR)
        self.assertEqual(succeeded, ["evt-1"])
        self.assertEqual(failed, [])
        kwargs["google_service"].batch_delete_google_meetings.assert_called_once_with(
            event_ids=["evt-1", "evt-2"], calendar_id=CALENDAR
        )


if __name__ == "__main__":
    unittest.main()
