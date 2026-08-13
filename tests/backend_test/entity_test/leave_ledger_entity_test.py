import datetime
import unittest
from decimal import Decimal

from backend.common.leave_enums import LeaveEntryType
from backend.entity.leave_ledger_entity import LeaveLedgerEntity


def _job_written_index():
    return next(
        index
        for index in LeaveLedgerEntity.__table__.indexes
        if index.name == "uq_leave_ledger_job_written_entry"
    )


class TestLeaveLedgerEntity(unittest.TestCase):
    def test_entry_carries_a_signed_hour_amount_and_its_reason(self):
        entry = LeaveLedgerEntity(
            user_id=1,
            entry_type=LeaveEntryType.LEAVE_DEDUCTION,
            hours=Decimal("-8.00"),
            effective_date=datetime.date(2026, 3, 2),
            source_request_id=7,
        )

        self.assertEqual(entry.__tablename__, "leave_ledger")
        self.assertEqual(entry.entry_type, LeaveEntryType.LEAVE_DEDUCTION)
        self.assertEqual(entry.hours, Decimal("-8.00"))
        self.assertEqual(entry.effective_date, datetime.date(2026, 3, 2))

    def test_the_double_write_guard_covers_only_what_a_job_writes(self):
        """The test is "did a cron write it", not "was it automatic". Adding
        manual_adjustment here would reject an admin's second correction for
        the same person on the same day, which is a legitimate entry."""
        where = str(_job_written_index().dialect_options["postgresql"]["where"])

        self.assertIn(LeaveEntryType.WEEKLY_ACCRUAL.value, where)
        self.assertIn(LeaveEntryType.CARRYOVER_FORFEIT.value, where)
        self.assertNotIn(LeaveEntryType.MANUAL_ADJUSTMENT.value, where)
        self.assertNotIn(LeaveEntryType.REVERSAL.value, where)

    def test_the_double_write_guard_is_keyed_on_user_type_and_date(self):
        index = _job_written_index()

        self.assertTrue(index.unique)
        self.assertEqual(
            [column.name for column in index.columns],
            ["user_id", "entry_type", "effective_date"],
        )

    def test_the_ledger_has_no_updated_timestamp(self):
        """Rows are never edited. A cancellation writes a reversal against the
        original, so an updated column would only ever record a mistake."""
        self.assertNotIn("updated_timestamp", LeaveLedgerEntity.__table__.c)

    def test_created_by_is_nullable_because_a_job_has_no_person_behind_it(self):
        self.assertTrue(LeaveLedgerEntity.__table__.c.created_by.nullable)


class TestLeaveEntryType(unittest.TestCase):
    def test_the_entry_types_are_exactly_the_six_the_design_settled_on(self):
        """holiday_grant went away with the public-holiday conversion. It is
        still in git history; it must not come back from there."""
        self.assertEqual(
            {entry.value for entry in LeaveEntryType},
            {
                "weekly_accrual",
                "leave_deduction",
                "exchange_credit",
                "manual_adjustment",
                "reversal",
                "carryover_forfeit",
            },
        )


if __name__ == "__main__":
    unittest.main()
