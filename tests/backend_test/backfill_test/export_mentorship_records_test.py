import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from backend.backfill.export_mentorship_records import completed_on_time
from backend.common.mentorship_enums import TrainingStatus


def _training(status, completed_timestamp, deadline):
    training = MagicMock()
    training.status = status
    training.completed_timestamp = completed_timestamp
    training.deadline = deadline
    return training


class TestCompletedOnTime(unittest.TestCase):
    def test_missing_training_is_not_on_time(self):
        self.assertFalse(completed_on_time(None))

    def test_incomplete_training_is_not_on_time(self):
        now = datetime.now(timezone.utc)
        training = _training(TrainingStatus.TO_DO, None, now)
        self.assertFalse(completed_on_time(training))

    def test_done_within_one_grace_day_is_on_time(self):
        deadline = datetime(2026, 7, 1, tzinfo=timezone.utc)
        training = _training(
            TrainingStatus.DONE, deadline + timedelta(hours=12), deadline
        )
        self.assertTrue(completed_on_time(training))

    def test_done_past_the_grace_day_is_late(self):
        deadline = datetime(2026, 7, 1, tzinfo=timezone.utc)
        training = _training(
            TrainingStatus.DONE, deadline + timedelta(days=2), deadline
        )
        self.assertFalse(completed_on_time(training))

    def test_done_with_no_deadline_is_on_time(self):
        # A row created at admission carries no deadline. There is no date to
        # miss, so a completed row counts as on time rather than crashing on
        # `None + timedelta`.
        training = _training(
            TrainingStatus.DONE, datetime(2026, 7, 1, tzinfo=timezone.utc), None
        )
        self.assertTrue(completed_on_time(training))

    def test_done_with_no_completed_timestamp_is_not_on_time(self):
        deadline = datetime(2026, 7, 1, tzinfo=timezone.utc)
        training = _training(TrainingStatus.DONE, None, deadline)
        self.assertFalse(completed_on_time(training))


if __name__ == "__main__":
    unittest.main()
