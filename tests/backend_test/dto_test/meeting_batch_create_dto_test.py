import unittest
from datetime import date, timedelta

from pydantic import ValidationError

from backend.dto.meeting_batch_create_dto import MeetingBatchCreateDto


class TestMeetingBatchCreateDto(unittest.TestCase):
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
        dto = MeetingBatchCreateDto(**self._valid_kwargs())
        self.assertEqual(dto.timezone, "America/New_York")
        self.assertEqual(dto.start_time, "10:00")
        self.assertEqual(dto.duration_minutes, 30)

    def test_invalid_timezone_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["timezone"] = "Mars/Phobos"
        with self.assertRaises(ValidationError):
            MeetingBatchCreateDto(**kwargs)

    def test_invalid_start_time_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["start_time"] = "9am"
        with self.assertRaises(ValidationError):
            MeetingBatchCreateDto(**kwargs)

    def test_invalid_duration_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["duration_minutes"] = 25
        with self.assertRaises(ValidationError):
            MeetingBatchCreateDto(**kwargs)

    def test_extra_field_forbidden(self):
        kwargs = self._valid_kwargs()
        kwargs["start_datetime"] = "2026-07-30T14:00:00Z"
        with self.assertRaises(ValidationError):
            MeetingBatchCreateDto(**kwargs)

    def test_defaults_to_single_weekly(self):
        dto = MeetingBatchCreateDto(**self._valid_kwargs())
        self.assertEqual(dto.count, 1)
        self.assertEqual(dto.interval_weeks, 1)

    def test_accepts_biweekly_multi_session(self):
        kwargs = self._valid_kwargs()
        kwargs["interval_weeks"] = 2
        kwargs["count"] = 12
        dto = MeetingBatchCreateDto(**kwargs)
        self.assertEqual(dto.interval_weeks, 2)
        self.assertEqual(dto.count, 12)

    def test_rejects_interval_weeks_out_of_set(self):
        for bad in (0, 3, 4):
            kwargs = self._valid_kwargs()
            kwargs["interval_weeks"] = bad
            with self.assertRaises(ValidationError):
                MeetingBatchCreateDto(**kwargs)

    def test_rejects_count_out_of_range(self):
        for bad in (0, 13, 100):
            kwargs = self._valid_kwargs()
            kwargs["count"] = bad
            with self.assertRaises(ValidationError):
                MeetingBatchCreateDto(**kwargs)

    def test_rejects_meeting_start_datetime_in_the_past(self):
        kwargs = self._valid_kwargs()
        kwargs["start_date"] = date.today() - timedelta(days=1)
        with self.assertRaises(ValidationError):
            MeetingBatchCreateDto(**kwargs)


if __name__ == "__main__":
    unittest.main()
