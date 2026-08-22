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
        self.assertEqual(accrual_start_date(2027, date(2024, 3, 5)), date(2027, 1, 1))

    def test_someone_hired_on_january_first_starts_that_day(self):
        self.assertEqual(accrual_start_date(2026, date(2026, 1, 1)), date(2026, 1, 1))

    def test_someone_hired_mid_year_starts_on_their_hire_date(self):
        self.assertEqual(accrual_start_date(2026, date(2026, 9, 2)), date(2026, 9, 2))

    def test_the_year_the_system_launches_is_not_treated_specially(self):
        """Launching in September does not shorten 2026 for someone employed
        since 2024: the engine computes this year from 1 January and pays the
        difference on its first run. That is deliberate. What an admin keys in
        by hand at launch is the balance carried in from the previous year, and
        nothing of this year's accrual, so there is nothing for this to land on
        top of."""
        self.assertEqual(accrual_start_date(2026, date(2024, 3, 5)), date(2026, 1, 1))


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

    def test_the_first_run_pays_the_year_to_date_in_one_go(self):
        """Someone hired in 2024, the engine's first run ever landing on 9/8.
        It owes 35 weeks because it owes the year, not because a run was
        missed -- the two are the same thing to this formula, and here they are
        the same thing in fact. The opening balance beside it carries only what
        came in from the previous year."""
        owed = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            accrual_start_date(2026, date(2024, 3, 5)),
            date(2026, 9, 8),
            Decimal("0.00"),
        )

        self.assertEqual(owed, Decimal("53.85"))

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


class TestALevelChange(unittest.TestCase):
    """An L1 has no entitlement at all, so the only level move that changes any
    number is the one across that line -- L2, L3 and L4 all sit at 80h. The
    target formula reads the level as it is now and applies it to the whole
    year, so without being told when the level changed it cannot tell a
    promotion apart from a run that never happened: both look like "owed more
    than granted"."""

    def test_a_promotion_pays_from_the_promotion_and_not_before(self):
        """An L1 promoted to L3 on 7/1, first run a week later. 40h would be
        six months of an entitlement they did not hold."""
        owed = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 7, 8),
            Decimal("0.00"),
            level_since=date(2026, 7, 1),
            granted_before_level_since=Decimal("0.00"),
        )

        self.assertEqual(owed, Decimal("1.54"))
        self.assertNotEqual(owed, Decimal("40.00"))

    def test_hours_earned_before_the_change_are_kept_not_recomputed(self):
        """An L3 who has been accruing all year and changes level in July keeps
        what the ledger already holds; only the weeks after the change are
        computed at the new rate."""
        owed = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 7, 8),
            Decimal("40.00"),
            level_since=date(2026, 7, 1),
            granted_before_level_since=Decimal("40.00"),
        )

        self.assertEqual(owed, Decimal("1.54"))

    def test_a_demotion_stops_accrual_without_clawing_anything_back(self):
        """L3 down to L1 on 7/1. The target freezes at what was already
        granted, so the run owes nothing -- and never a negative number."""
        owed = weekly_accrual_hours(
            L1_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 9, 2),
            Decimal("40.00"),
            level_since=date(2026, 7, 1),
            granted_before_level_since=Decimal("40.00"),
        )

        self.assertEqual(owed, Decimal("0.00"))

    def test_someone_who_never_changed_level_is_unaffected(self):
        """No level_change row means no arguments, and the arithmetic has to be
        identical to the plain formula -- this is almost everybody."""
        with_defaults = weekly_accrual_hours(
            L3_ANNUAL_HOURS, date(2026, 1, 1), date(2026, 7, 8), Decimal("0.00")
        )

        self.assertEqual(with_defaults, Decimal("40.00"))

    def test_a_change_observed_before_the_accrual_start_is_not_a_split(self):
        """A change dated in a previous year, or before go-live, is simply how
        this year begins: the whole year is already at that entitlement. The
        hours passed for "before the change" are not part of this year and must
        not be added on top of it -- doing so would pay them twice."""
        owed = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 7, 8),
            Decimal("0.00"),
            level_since=date(2025, 11, 3),
            granted_before_level_since=Decimal("60.00"),
        )

        self.assertEqual(owed, Decimal("40.00"))


class TestSettlingTheOldYear(unittest.TestCase):
    """Week 52 needs 364 elapsed days -- 31 December, or the 30th in a leap
    year -- and the weekly job runs on one fixed weekday, so it reaches that
    week about one year in seven. Every other year its last run stops at week
    51 and the reset on 1 January puts the rest out of reach. The annual job
    settles the closing year by running the same arithmetic at 31 December."""

    def test_an_ordinary_year_is_short_until_it_is_settled(self):
        """The last weekly run of 2026 lands on the 27th at the latest, which
        is week 51 of 52: 78.46 of 80. Nothing raises."""
        last_weekly_run = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 12, 27),
            Decimal("76.92"),
        )

        self.assertEqual(last_weekly_run, Decimal("1.54"))
        self.assertEqual(Decimal("76.92") + last_weekly_run, Decimal("78.46"))

    def test_settling_at_december_31st_closes_the_gap(self):
        settlement = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 12, 31),
            Decimal("78.46"),
        )

        self.assertEqual(settlement, Decimal("1.54"))
        self.assertEqual(Decimal("78.46") + settlement, Decimal("80.00"))

    def test_settling_a_year_already_settled_owes_nothing(self):
        """The annual job runs unconditionally rather than looking for a year
        that was missed, so the ordinary case has to be a no-op."""
        self.assertEqual(
            weekly_accrual_hours(
                L3_ANNUAL_HOURS,
                date(2026, 1, 1),
                date(2026, 12, 31),
                Decimal("80.00"),
            ),
            Decimal("0.00"),
        )

    def test_a_settlement_respects_a_level_change_in_the_closing_year(self):
        """Someone promoted in July closes the year on the weeks they held the
        higher level, not on the whole year."""
        settlement = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 12, 31),
            Decimal("0.00"),
            level_since=date(2026, 7, 1),
            granted_before_level_since=Decimal("0.00"),
        )

        self.assertEqual(settlement, Decimal("40.00"))


if __name__ == "__main__":
    unittest.main()
