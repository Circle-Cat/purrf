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
    LevelChange,
    accrual_start_date,
    accrual_target_hours,
    carryover_effective_date,
    carryover_forfeit_hours,
    format_hours,
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
    number is the one across that line -- L2, L3 and L4 all sit at 80h.

    The credited days are the whole weeks since the start of accrual, as for
    everybody, and each of those days is paid at the entitlement held on it.
    2026 starts on a Thursday and 1 July is its 182nd day, so a change on 7/1
    leaves 181 days before it."""

    PROMOTION = LevelChange(date(2026, 7, 1), L1_ANNUAL_HOURS, L3_ANNUAL_HOURS)
    DEMOTION = LevelChange(date(2026, 7, 1), L3_ANNUAL_HOURS, L1_ANNUAL_HOURS)

    def test_a_promotion_pays_from_the_promotion_and_not_before(self):
        """26 whole weeks by 7/8 credit days up to and including 7/1, the one
        day at 80h. 40h would be six months of an entitlement they did not
        hold."""
        owed = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 7, 8),
            Decimal("0.00"),
            level_changes=[self.PROMOTION],
        )

        self.assertEqual(owed, Decimal("0.22"))

    def test_the_week_after_a_promotion_catches_up_to_the_weekly_rate(self):
        """By 7/15 eight days are at 80h: 1.76 in all, 1.54 more than the
        0.22 already paid."""
        owed = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 7, 15),
            Decimal("0.22"),
            level_changes=[self.PROMOTION],
        )

        self.assertEqual(owed, Decimal("1.54"))

    def test_a_demotion_stops_accrual_without_clawing_anything_back(self):
        """The 181 days at 80h come to 39.78. A ledger already ahead of that
        owes nothing, and never a negative number."""
        owed = weekly_accrual_hours(
            L1_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 9, 2),
            Decimal("40.00"),
            level_changes=[self.DEMOTION],
        )

        self.assertEqual(owed, Decimal("0.00"))

    def test_someone_who_never_changed_level_is_unaffected(self):
        """No level_change row means no arguments, and the arithmetic has to be
        identical to the plain formula -- this is almost everybody."""
        with_defaults = weekly_accrual_hours(
            L3_ANNUAL_HOURS, date(2026, 1, 1), date(2026, 7, 8), Decimal("0.00")
        )

        self.assertEqual(with_defaults, Decimal("40.00"))

    def test_a_change_before_the_accrual_start_sets_the_whole_year(self):
        """A change in a previous year is simply how this year begins."""
        owed = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 7, 8),
            Decimal("0.00"),
            level_changes=[
                LevelChange(date(2025, 11, 3), L1_ANNUAL_HOURS, L3_ANNUAL_HOURS)
            ],
        )

        self.assertEqual(owed, Decimal("40.00"))

    def test_the_entitlement_comes_from_the_ledger_not_the_current_level(self):
        """Once a change is on record, the hours it recorded decide each day.
        The current level is only for somebody with no change at all."""
        owed = weekly_accrual_hours(
            L1_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 7, 8),
            Decimal("0.00"),
            level_changes=[
                LevelChange(date(2025, 11, 3), L1_ANNUAL_HOURS, L3_ANNUAL_HOURS)
            ],
        )

        self.assertEqual(owed, Decimal("40.00"))

    def test_a_level_raised_and_put_back_on_one_day_ends_where_it_was_put(self):
        """Two rows on one date are read in the order they were written."""
        owed = weekly_accrual_hours(
            L1_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 12, 31),
            Decimal("0.00"),
            level_changes=[
                self.PROMOTION,
                LevelChange(date(2026, 7, 1), L3_ANNUAL_HOURS, L1_ANNUAL_HOURS),
            ],
        )

        self.assertEqual(owed, Decimal("0.00"))


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

    def test_a_settlement_pays_a_promotion_from_its_day_to_the_year_end(self):
        """Promoted on 7/1: 183 of the year's 364 credited days at 80h. Counting
        whole weeks from the promotion instead left the last day unpaid at
        40.00."""
        settlement = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 12, 31),
            Decimal("0.00"),
            level_changes=[TestALevelChange.PROMOTION],
        )

        self.assertEqual(settlement, Decimal("40.22"))

    def test_a_settlement_pays_the_days_before_a_demotion(self):
        """The last weekly run before a 7/1 demotion, on 6/25, had paid 25
        weeks: 38.46. The six days from then to the change are still owed at
        80h, which brings the year to 39.78."""
        settlement = weekly_accrual_hours(
            L1_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 12, 31),
            Decimal("38.46"),
            level_changes=[TestALevelChange.DEMOTION],
        )

        self.assertEqual(settlement, Decimal("1.32"))

    def test_a_settlement_reads_every_change_in_the_year(self):
        """Down to L1 on 4/10 (day 100) and back up on 9/7 (day 250): 99 days
        and then 115 days at 80h."""
        settlement = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 12, 31),
            Decimal("0.00"),
            level_changes=[
                LevelChange(date(2026, 4, 10), L3_ANNUAL_HOURS, L1_ANNUAL_HOURS),
                LevelChange(date(2026, 9, 7), L1_ANNUAL_HOURS, L3_ANNUAL_HOURS),
            ],
        )

        self.assertEqual(settlement, Decimal("47.03"))

    def test_a_late_settlement_ignores_a_promotion_made_after_the_year(self):
        """An L1 all year, promoted on 1 January. A settlement re-run on the
        2nd reads the current level as 80h, but the change on record says the
        year being closed was at 0h."""
        settlement = weekly_accrual_hours(
            L3_ANNUAL_HOURS,
            date(2026, 1, 1),
            date(2026, 12, 31),
            Decimal("0.00"),
            level_changes=[
                LevelChange(date(2027, 1, 1), L1_ANNUAL_HOURS, L3_ANNUAL_HOURS)
            ],
        )

        self.assertEqual(settlement, Decimal("0.00"))


class TestFormatHours(unittest.TestCase):
    """How an hour figure is written down wherever it leaves the module."""

    def test_a_whole_number_of_hours_keeps_both_decimals(self):
        """80 reads as 80.00, not 80 -- a balance is a money-shaped figure and
        a dropped decimal reads as a different kind of number."""
        self.assertEqual(format_hours(Decimal("80")), "80.00")

    def test_an_exponent_is_written_out_rather_than_shown(self):
        """``str`` on this Decimal yields ``1E+2``. A report is read by people
        and a wire value is parsed by a page, and neither wants that."""
        self.assertEqual(format_hours(Decimal("1E+2")), "100.00")

    def test_a_forfeit_keeps_its_sign(self):
        """Forfeits are negative rows, and the report shows them as such."""
        self.assertEqual(format_hours(Decimal("-1.54")), "-1.54")


if __name__ == "__main__":
    unittest.main()
