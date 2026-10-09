import unittest
from datetime import datetime, timedelta, timezone
import asyncio
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from backend.backfill.export_mentorship_records import (
    completed_on_time,
    compute_ineligible_mentee_ids,
    fetch_participants_data,
)
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


def _sql_of(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


def _session_returning_nothing():
    result = MagicMock()
    result.all.return_value = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


class TestLeaversAreLeftOut(unittest.TestCase):
    """Rejected and withdrawn registrations are both people who left."""

    def test_the_eligibility_query_skips_both(self):
        session = _session_returning_nothing()

        asyncio.run(compute_ineligible_mentee_ids(session, 5, None, set()))

        sql = _sql_of(session.execute.await_args_list[0].args[0])
        self.assertIn("NOT IN ('rejected', 'withdrawn')", sql)

    def test_the_export_query_skips_both(self):
        session = _session_returning_nothing()

        asyncio.run(fetch_participants_data(session, 5))

        sql = _sql_of(session.execute.await_args_list[0].args[0])
        self.assertIn("NOT IN ('rejected', 'withdrawn')", sql)


if __name__ == "__main__":
    unittest.main()
