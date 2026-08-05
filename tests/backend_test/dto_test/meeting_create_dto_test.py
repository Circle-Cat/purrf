import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from pydantic import ValidationError

from backend.dto.meeting_create_dto import MeetingCreateDto


class TestMeetingCreateDto(unittest.TestCase):
    _FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def setUp(self):
        patcher = patch("backend.dto.meeting_create_dto.datetime")
        mock_datetime = patcher.start()
        mock_datetime.now.return_value = self._FIXED_NOW
        self.addCleanup(patcher.stop)

    def _completed_meeting_kwargs(self, end_datetime):
        return dict(
            round_id=1,
            start_datetime=end_datetime - timedelta(hours=1),
            end_datetime=end_datetime,
            is_completed=True,
        )

    def test_rejects_completed_meeting_ending_in_the_future(self):
        future = self._FIXED_NOW + timedelta(hours=1)
        with self.assertRaises(ValidationError):
            MeetingCreateDto(**self._completed_meeting_kwargs(end_datetime=future))

    def test_allows_completed_meeting_that_already_ended(self):
        past = self._FIXED_NOW - timedelta(hours=1)
        dto = MeetingCreateDto(**self._completed_meeting_kwargs(end_datetime=past))
        self.assertTrue(dto.is_completed)

    def test_allows_completed_meeting_ending_exactly_now(self):
        dto = MeetingCreateDto(
            **self._completed_meeting_kwargs(end_datetime=self._FIXED_NOW)
        )
        self.assertTrue(dto.is_completed)


if __name__ == "__main__":
    unittest.main()
