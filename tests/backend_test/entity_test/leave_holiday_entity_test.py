import datetime
import unittest

from backend.entity.leave_holiday_entity import LeaveHolidayEntity


class TestLeaveHolidayEntity(unittest.TestCase):
    def test_holiday_carries_year_date_name_and_exchangeability(self):
        holiday = LeaveHolidayEntity(
            year=2026,
            date=datetime.date(2026, 10, 1),
            name="National Day",
            is_exchangeable=True,
        )

        self.assertEqual(holiday.__tablename__, "leave_holiday")
        self.assertEqual(holiday.year, 2026)
        self.assertEqual(holiday.date, datetime.date(2026, 10, 1))
        self.assertEqual(holiday.name, "National Day")
        self.assertTrue(holiday.is_exchangeable)

    def test_year_and_date_are_unique_together_with_year_leading(self):
        """The leading column matters: "has 2027 been entered?" is answered by
        an existence lookup on this index, and that is a hard gate on every
        request submission."""
        unique = [
            constraint
            for constraint in LeaveHolidayEntity.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        ]

        self.assertEqual(len(unique), 1)
        self.assertEqual(
            [column.name for column in unique[0].columns], ["year", "date"]
        )

    def test_a_check_constraint_ties_the_redundant_year_to_the_date(self):
        """year duplicates information already in date, so nothing but the
        database can stop the two from drifting apart."""
        checks = [
            str(constraint.sqltext)
            for constraint in LeaveHolidayEntity.__table__.constraints
            if constraint.__class__.__name__ == "CheckConstraint"
        ]

        self.assertEqual(len(checks), 1)
        self.assertIn("EXTRACT(YEAR FROM date)", checks[0])

    def test_the_table_has_no_region_column(self):
        """Admission rejects anyone outside China, so the dimension has one
        value. Reintroducing it costs a backfill and a new unique index."""
        self.assertNotIn("region", LeaveHolidayEntity.__table__.c)


if __name__ == "__main__":
    unittest.main()
