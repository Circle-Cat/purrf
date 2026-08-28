"""The leave constants, and the read-only view of them the page renders."""

import datetime
import unittest
from unittest.mock import patch

from backend.leave.employment_profile import ANNUAL_HOURS_BY_LEVEL
from backend.leave.leave_policy import (
    HOURS_PER_DAY,
    MAX_CARRYOVER_HOURS,
    MAX_OVERDRAFT_HOURS,
    WEEKEND_WEEKDAYS,
    current_policy,
)


class TestWeekend(unittest.TestCase):
    def test_the_working_week_runs_tuesday_to_saturday(self):
        """Sunday and Monday are the days off, in datetime.weekday() numbering
        where Monday is 0."""
        self.assertEqual(WEEKEND_WEEKDAYS, (6, 0))

    def test_every_label_names_the_day_its_number_means(self):
        """The labels are rendered server-side because JavaScript's getDay()
        numbers Sunday as 0 while weekday() numbers Monday as 0. This checks
        the pair by a route that does not reuse the mapping under test."""
        policy = current_policy()

        for weekday, label in zip(policy.weekend_weekdays, policy.weekend_labels):
            a_day_with_that_weekday = next(
                datetime.date(2026, 1, day)
                for day in range(1, 8)
                if datetime.date(2026, 1, day).weekday() == weekday
            )

            self.assertEqual(a_day_with_that_weekday.strftime("%A"), label)


class TestCurrentPolicy(unittest.TestCase):
    def test_a_working_day_is_eight_hours(self):
        self.assertEqual(current_policy().hours_per_day, HOURS_PER_DAY)
        self.assertEqual(HOURS_PER_DAY, 8)

    def test_the_annual_hours_are_the_ones_the_engine_uses(self):
        """Compared against the accrual side's own table, so a second copy of
        the level hours fails here the moment the two drift. Identity cannot be
        asserted: pydantic copies the dict on the way into the model."""
        self.assertEqual(current_policy().annual_hours_by_level, ANNUAL_HOURS_BY_LEVEL)

    def test_an_unset_ceiling_stays_none_rather_than_becoming_zero(self):
        """None means "not in force". Zero would mean "not one hour may be
        carried over", which is a different policy."""
        self.assertIsNone(MAX_CARRYOVER_HOURS)
        self.assertIsNone(MAX_OVERDRAFT_HOURS)
        self.assertIsNone(current_policy().max_carryover_hours)
        self.assertIsNone(current_policy().max_overdraft_hours)

    @patch("backend.leave.leave_policy.MAX_OVERDRAFT_HOURS", 0)
    @patch("backend.leave.leave_policy.MAX_CARRYOVER_HOURS", 40)
    def test_a_ceiling_that_is_set_reaches_the_page_unchanged(self):
        """Read at call time, not frozen at import: a value of 0 has to arrive
        as 0 and not be mistaken for "unset"."""
        policy = current_policy()

        self.assertEqual(policy.max_carryover_hours, 40)
        self.assertEqual(policy.max_overdraft_hours, 0)


if __name__ == "__main__":
    unittest.main()
