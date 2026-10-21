import unittest
from datetime import date, timedelta

from pydantic import ValidationError

from backend.dto.meeting_reschedule_dto import MeetingRescheduleDto


class TestMeetingRescheduleDto(unittest.TestCase):
    def _valid_kwargs(self):
        return dict(
            round_id=1,
            partner_id=2,
            timezone="America/New_York",
            start_date=date.today() + timedelta(days=1),
            start_time="10:00",
            duration_minutes=30,
        )

    def test_valid_payload(self):
        dto = MeetingRescheduleDto(**self._valid_kwargs())
        self.assertEqual(dto.timezone, "America/New_York")
        self.assertEqual(dto.start_time, "10:00")
        self.assertEqual(dto.duration_minutes, 30)

    def test_invalid_timezone_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["timezone"] = "Mars/Phobos"
        with self.assertRaises(ValidationError):
            MeetingRescheduleDto(**kwargs)

    def test_invalid_start_time_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["start_time"] = "10-00"
        with self.assertRaises(ValidationError):
            MeetingRescheduleDto(**kwargs)

    def test_unsupported_duration_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["duration_minutes"] = 25
        with self.assertRaises(ValidationError):
            MeetingRescheduleDto(**kwargs)

    def test_past_start_rejected(self):
        # A meeting may be moved, but not into the past.
        kwargs = self._valid_kwargs()
        kwargs["start_date"] = date.today() - timedelta(days=1)
        with self.assertRaises(ValidationError):
            MeetingRescheduleDto(**kwargs)

    def test_recurrence_fields_are_not_accepted(self):
        # Rescheduling moves one meeting; a series is out of scope, and
        # silently ignoring `count` would be worse than rejecting it.
        kwargs = self._valid_kwargs()
        kwargs["count"] = 3
        with self.assertRaises(ValidationError):
            MeetingRescheduleDto(**kwargs)


if __name__ == "__main__":
    unittest.main()
