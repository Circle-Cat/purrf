"""Acceptance cases for the two leave accrual jobs, written before the code.

Every expected number here is worked out from the design and fixed. The job of
the implementation is to make them pass without editing them; a number that
looks wrong is a question to ask, not a line to change.

Two rules this file cannot reach live in the ledger query the weekly job uses
to work out ``granted_this_year``, and need their own test against the
database: it must sum ``weekly_accrual`` rows only, and only those dated inside
the year being accrued for. Both failures are silent and both are expensive --
see ``weekly_accrual_hours``.

``TestDecisionsStillOpen`` at the bottom is skipped on purpose. Those cases have
no agreed answer yet, so the expected values in them are a proposal.
"""

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from backend.leave.leave_accrual import (
    accrual_start_date,
    accrual_target_hours,
    carryover_effective_date,
    carryover_forfeit_hours,
    weekly_accrual_hours,
    weeks_passed,
)
from backend.leave.leave_clock import business_today

L1_ANNUAL_HOURS = 0
L3_ANNUAL_HOURS = 80

GO_LIVE = date(2026, 9, 1)


def _clock_fixed_at(instant):
    """Stands in for a wall clock stopped at one UTC instant.

    Reading it without naming a zone yields the UTC wall time, which is what
    makes the Beijing-day tests able to fail.
    """
    return lambda tz=None: (
        instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    )


class TestTheClockAgainstTheForfeitDate(unittest.TestCase):
    """business_today itself is covered in leave_clock_test. What this class is
    for is the pair: the annual job's schedule sits in the window where the two
    dates disagree, and the date it stamps is derived from "today"."""

    @patch("backend.leave.leave_clock.datetime")
    def test_the_forfeit_lands_on_december_31st_when_the_job_runs_in_that_window(
        self, mock_datetime
    ):
        """The annual job scheduled at 20:00 UTC on the 31st runs at 04:00
        Beijing on the 1st. Read as UTC, "last year's end" comes out as the
        30th and the forfeit is dated a day early."""
        mock_datetime.now.side_effect = _clock_fixed_at(
            datetime(2026, 12, 31, 20, 0, tzinfo=timezone.utc)
        )

        self.assertEqual(business_today(), date(2027, 1, 1))
        self.assertEqual(carryover_effective_date(business_today()), date(2026, 12, 31))


class TestAccrualStartDate(unittest.TestCase):
    def test_a_long_serving_employee_starts_at_january_first(self):
        self.assertEqual(
            accrual_start_date(2027, date(2024, 3, 5), GO_LIVE), date(2027, 1, 1)
        )

    def test_someone_hired_mid_year_starts_on_their_hire_date(self):
        self.assertEqual(
            accrual_start_date(2026, date(2026, 9, 2), date(2025, 1, 1)),
            date(2026, 9, 2),
        )

    def test_go_live_wins_over_an_older_hire_date(self):
        """Otherwise the first run after launch pays the year to date to
        everyone already employed, on top of the opening balance that already
        covers it."""
        self.assertEqual(accrual_start_date(2026, date(2024, 3, 5), GO_LIVE), GO_LIVE)

    def test_go_live_stops_mattering_the_following_year(self):
        self.assertEqual(
            accrual_start_date(2027, date(2024, 3, 5), GO_LIVE), date(2027, 1, 1)
        )


class TestWeeksPassed(unittest.TestCase):
    def test_a_week_is_credited_only_once_seven_days_have_elapsed(self):
        start = date(2026, 1, 1)

        for days, expected in ((0, 0), (6, 0), (7, 1), (13, 1), (14, 2)):
            with self.subTest(days=days):
                self.assertEqual(
                    weeks_passed(start, start + timedelta(days=days)), expected
                )

    def test_a_whole_year_is_fifty_two_weeks(self):
        self.assertEqual(weeks_passed(date(2026, 1, 1), date(2026, 12, 31)), 52)

    def test_a_leap_year_is_still_fifty_two_weeks(self):
        """The extra day would make a 53rd week pay a 53/52 target."""
        self.assertEqual(weeks_passed(date(2028, 1, 1), date(2028, 12, 31)), 52)


class TestAccrualTargetHours(unittest.TestCase):
    def test_the_worked_examples_from_the_design(self):
        for weeks, expected in (
            (17, "26.15"),  # hired 9/2, at year end
            (8, "12.31"),  # hired 1/1, left 3/1
            (4, "6.15"),  # hired in December
            (52, "80.00"),  # a full year
        ):
            with self.subTest(weeks=weeks):
                self.assertEqual(
                    accrual_target_hours(L3_ANNUAL_HOURS, weeks), Decimal(expected)
                )

    def test_the_target_is_rounded_rather_than_truncated(self):
        """One week of 80h is 1.5384..., and truncating loses a cent a week
        that the final week then has to hand back."""
        self.assertEqual(accrual_target_hours(L3_ANNUAL_HOURS, 1), Decimal("1.54"))

    def test_a_zero_entitlement_targets_zero_all_year(self):
        for weeks in (0, 1, 26, 52):
            with self.subTest(weeks=weeks):
                self.assertEqual(
                    accrual_target_hours(L1_ANNUAL_HOURS, weeks), Decimal("0.00")
                )


class TestWeeklyAccrualHours(unittest.TestCase):
    def test_the_weekly_amounts_add_up_to_the_annual_figure_exactly(self):
        """80 over 52 weeks does not divide evenly, so the weekly amounts
        alternate between 1.53 and 1.54 and the year still has to close on
        80.00."""
        granted = Decimal("0.00")
        for week in range(1, 53):
            granted += weekly_accrual_hours(
                L3_ANNUAL_HOURS,
                date(2026, 1, 1),
                date(2026, 1, 1) + timedelta(days=7 * week),
                granted,
            )

        self.assertEqual(granted, Decimal("80.00"))

    def test_the_first_run_after_go_live_pays_one_week_not_the_year_to_date(self):
        """Someone hired in 2024, launched on 9/1, first run a week later."""
        owed = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            accrual_start_date(2026, date(2024, 3, 5), GO_LIVE),
            date(2026, 9, 8),
            Decimal("0.00"),
        )

        self.assertEqual(owed, Decimal("1.54"))
        self.assertNotEqual(owed, Decimal("53.85"))

    def test_the_new_year_starts_paying_again_from_week_one(self):
        """They finished the previous year on the full 80h. The count that
        matters is what this year has granted, which is nothing."""
        self.assertEqual(
            weekly_accrual_hours(
                L3_ANNUAL_HOURS,
                date(2027, 1, 1),
                date(2027, 1, 8),
                Decimal("0.00"),
            ),
            Decimal("1.54"),
        )

    def test_counting_last_years_hours_as_well_stops_the_engine_dead(self):
        """Not a feature -- this is what a ledger sum that forgets to filter by
        year produces on the first run of January, and it keeps producing it
        every week for the rest of the year without raising anything."""
        self.assertEqual(
            weekly_accrual_hours(
                L3_ANNUAL_HOURS,
                date(2027, 1, 1),
                date(2027, 1, 8),
                Decimal("80.00"),
            ),
            Decimal("0.00"),
        )

    def test_a_missed_run_is_made_up_by_the_next_one(self):
        """The ledger stands at week 50's target and it is now week 52, so the
        two skipped weeks come out together rather than being lost."""
        self.assertEqual(
            weekly_accrual_hours(
                L3_ANNUAL_HOURS,
                date(2026, 1, 1),
                date(2026, 12, 31),
                Decimal("76.92"),
            ),
            Decimal("3.08"),
        )

    def test_running_twice_on_the_same_day_owes_nothing_the_second_time(self):
        self.assertEqual(
            weekly_accrual_hours(
                L3_ANNUAL_HOURS,
                date(2026, 1, 1),
                date(2026, 1, 8),
                Decimal("1.54"),
            ),
            Decimal("0.00"),
        )

    def test_a_zero_entitlement_owes_nothing_without_complaining(self):
        """The job still has to walk over these people. Filtering them out
        early means nothing reports it if the L1 figure ever stops being
        zero."""
        self.assertEqual(
            weekly_accrual_hours(
                L1_ANNUAL_HOURS,
                date(2026, 1, 1),
                date(2026, 7, 8),
                Decimal("0.00"),
            ),
            Decimal("0.00"),
        )

    def test_it_never_claws_hours_back(self):
        """A level that went down leaves the ledger ahead of the target. The
        ledger is append-only and a scheduled job is not the thing that should
        be deciding to reverse an entitlement."""
        self.assertEqual(
            weekly_accrual_hours(
                L1_ANNUAL_HOURS,
                date(2026, 1, 1),
                date(2026, 7, 8),
                Decimal("46.15"),
            ),
            Decimal("0.00"),
        )


class TestCarryoverForfeitHours(unittest.TestCase):
    def test_no_ceiling_means_nothing_is_ever_cut(self):
        self.assertEqual(
            carryover_forfeit_hours(Decimal("60.00"), None), Decimal("0.00")
        )

    def test_only_the_overshoot_is_cut(self):
        self.assertEqual(
            carryover_forfeit_hours(Decimal("60.00"), Decimal("40.00")),
            Decimal("-20.00"),
        )

    def test_a_balance_under_the_ceiling_is_untouched(self):
        self.assertEqual(
            carryover_forfeit_hours(Decimal("30.00"), Decimal("40.00")),
            Decimal("0.00"),
        )

    def test_a_balance_exactly_on_the_ceiling_is_untouched(self):
        self.assertEqual(
            carryover_forfeit_hours(Decimal("40.00"), Decimal("40.00")),
            Decimal("0.00"),
        )

    def test_a_negative_balance_carries_into_the_new_year_unchanged(self):
        """Year end is not debt forgiveness. People on a zero entitlement live
        in the red and the new year's accrual fills it back in."""
        self.assertEqual(
            carryover_forfeit_hours(Decimal("-16.00"), Decimal("40.00")),
            Decimal("0.00"),
        )

    def test_running_the_annual_job_twice_does_not_cut_twice(self):
        """The unique index stops a duplicate row from landing, but the
        arithmetic has to agree with it: after the first cut the balance is
        the ceiling, and a second pass over it owes nothing."""
        cap = Decimal("40.00")
        balance = Decimal("60.00")

        first = carryover_forfeit_hours(balance, cap)
        second = carryover_forfeit_hours(balance + first, cap)

        self.assertEqual(first, Decimal("-20.00"))
        self.assertEqual(second, Decimal("0.00"))


class TestCarryoverEffectiveDate(unittest.TestCase):
    def test_the_forfeit_is_dated_to_the_year_being_closed(self):
        """Dated to January 1st it reads as the new year opening by docking
        someone eight hours."""
        self.assertEqual(carryover_effective_date(date(2027, 1, 1)), date(2026, 12, 31))

    def test_a_late_rerun_still_dates_the_forfeit_to_december_31st(self):
        """The job is scheduled for the 1st, so "yesterday" and "the end of
        last year" happen to agree. A retry a day later separates them, and
        only one of the two stays inside the year being closed."""
        self.assertEqual(carryover_effective_date(date(2027, 1, 2)), date(2026, 12, 31))


@unittest.skip("No agreed answer yet -- the expected values below are a proposal.")
class TestDecisionsStillOpen(unittest.TestCase):
    def test_a_promotion_does_not_pay_out_the_months_before_it(self):
        """An L1 promoted to L3 on 7/1. The target formula reads their level as
        it is now and applies it to the whole year, so the next run hands over
        40h covering six months at an entitlement they did not have. The design
        says a promotion only affects accrual after it, which would be 1.54h.

        Satisfying this needs an input the function does not currently take:
        when the level changed. Azure keeps only the current value, so the
        choice is between purrf recording level changes as it observes them and
        accepting the windfall and writing it down.
        """
        self.assertEqual(
            weekly_accrual_hours(
                L3_ANNUAL_HOURS,
                date(2026, 1, 1),
                date(2026, 7, 8),
                Decimal("0.00"),
            ),
            Decimal("1.54"),
        )

    def test_a_run_missed_over_new_year_still_settles_the_old_year(self):
        """Catch-up stops at the year boundary. Last run 12/24 left the year at
        78.46 of 80; the run on 1/5 computes against the new year's target and
        owes nothing, so the last 1.54h is lost with nothing raised.

        The annual job already runs on 1/1 and already writes rows dated to
        12/31, so settling the old year there is the cheap fix -- but it has to
        happen before the ceiling is applied, or the hours it just paid get cut.
        """
        self.assertEqual(
            weekly_accrual_hours(
                L3_ANNUAL_HOURS,
                date(2026, 1, 1),
                date(2026, 12, 31),
                Decimal("78.46"),
            ),
            Decimal("1.54"),
        )


if __name__ == "__main__":
    unittest.main()
