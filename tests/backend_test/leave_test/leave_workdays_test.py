"""Working days, request hours, and the notice a request needed.

Every number in here is worked out from the design and fixed. The two examples
the design settles on -- the 16h deduction and the notice table -- appear
verbatim, on their real 2026 dates.

One definition of a working day serves both the deduction and the notice count.
A second definition is the kind of thing that agrees on most inputs and
disagrees on the ones nobody tries.
"""

import datetime
import unittest
from decimal import Decimal

from backend.common.leave_enums import LeaveRequestType
from backend.leave.leave_workdays import (
    count_workdays,
    days_not_counted,
    hours_by_day,
    is_workday,
    request_hours,
    required_notice_workdays,
    workdays_before,
)

# 2026-06-19 is the Dragon Boat Festival, a company holiday.
DRAGON_BOAT = frozenset({datetime.date(2026, 6, 19)})
NO_HOLIDAYS = frozenset()


class TestIsWorkday(unittest.TestCase):
    def test_the_working_week_runs_tuesday_to_saturday(self):
        by_day = {
            datetime.date(2026, 6, 16): True,  # Tuesday
            datetime.date(2026, 6, 17): True,  # Wednesday
            datetime.date(2026, 6, 18): True,  # Thursday
            datetime.date(2026, 6, 19): True,  # Friday
            datetime.date(2026, 6, 20): True,  # Saturday
            datetime.date(2026, 6, 21): False,  # Sunday
            datetime.date(2026, 6, 22): False,  # Monday
        }

        self.assertEqual({day: is_workday(day, NO_HOLIDAYS) for day in by_day}, by_day)

    def test_a_company_holiday_is_not_a_working_day(self):
        self.assertFalse(is_workday(datetime.date(2026, 6, 19), DRAGON_BOAT))


class TestCountWorkdays(unittest.TestCase):
    def test_both_ends_are_counted(self):
        self.assertEqual(
            count_workdays(
                datetime.date(2026, 6, 16), datetime.date(2026, 6, 18), NO_HOLIDAYS
            ),
            3,
        )

    def test_a_single_working_day_counts_one(self):
        self.assertEqual(
            count_workdays(
                datetime.date(2026, 6, 18), datetime.date(2026, 6, 18), NO_HOLIDAYS
            ),
            1,
        )

    def test_a_range_of_nothing_but_days_off_counts_none(self):
        self.assertEqual(
            count_workdays(
                datetime.date(2026, 6, 21), datetime.date(2026, 6, 22), NO_HOLIDAYS
            ),
            0,
        )


class TestRequestHours(unittest.TestCase):
    def test_the_worked_example_from_the_design(self):
        """18 June to 22 June 2026: the 19th is the Dragon Boat Festival, the
        21st is a Sunday and the 22nd a Monday. Two working days are left."""
        hours = request_hours(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 18),
            datetime.date(2026, 6, 22),
            None,
            None,
            DRAGON_BOAT,
        )

        self.assertEqual(hours, Decimal("16.00"))

    def test_a_range_is_always_whole_days(self):
        """A range carries no times at all, so there is nothing to apply."""
        hours = request_hours(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 17),
            datetime.date(2026, 6, 18),
            None,
            None,
            NO_HOLIDAYS,
        )

        self.assertEqual(hours, Decimal("16.00"))

    def test_one_day_without_times_is_a_whole_day(self):
        hours = request_hours(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 18),
            datetime.date(2026, 6, 18),
            None,
            None,
            NO_HOLIDAYS,
        )

        self.assertEqual(hours, Decimal("8.00"))

    def test_one_day_with_times_is_the_span_between_them(self):
        hours = request_hours(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 18),
            datetime.date(2026, 6, 18),
            datetime.time(9, 0),
            datetime.time(13, 30),
            NO_HOLIDAYS,
        )

        self.assertEqual(hours, Decimal("4.50"))

    def test_a_range_carrying_times_is_refused(self):
        """Ignoring them stored a whole-day figure alongside times the entity's
        CHECK constraint forbids, so the write failed at flush and the caller
        got a 500 rather than an answer."""
        with self.assertRaises(ValueError):
            request_hours(
                LeaveRequestType.PAID,
                datetime.date(2026, 6, 17),
                datetime.date(2026, 6, 19),
                datetime.time(9, 0),
                datetime.time(13, 0),
                NO_HOLIDAYS,
            )

    def test_a_start_time_without_an_end_is_refused(self):
        """One time says when, never how long. Treating it as a whole day both
        overstates the request and leaves a stray time on the row."""
        with self.assertRaises(ValueError):
            request_hours(
                LeaveRequestType.PAID,
                datetime.date(2026, 6, 18),
                datetime.date(2026, 6, 18),
                datetime.time(9, 0),
                None,
                NO_HOLIDAYS,
            )

    def test_an_end_time_without_a_start_is_refused(self):
        """The mirror image, and the likelier of the two to be a client bug."""
        with self.assertRaises(ValueError):
            request_hours(
                LeaveRequestType.PAID,
                datetime.date(2026, 6, 18),
                datetime.date(2026, 6, 18),
                None,
                datetime.time(13, 0),
                NO_HOLIDAYS,
            )

    def test_a_day_that_is_not_a_working_day_is_worth_nothing(self):
        """Nothing to deduct: the office is shut. The caller refuses a request
        of zero hours rather than storing one."""
        hours = request_hours(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 19),
            datetime.date(2026, 6, 19),
            None,
            None,
            DRAGON_BOAT,
        )

        self.assertEqual(hours, Decimal("0.00"))

    def test_times_off_the_half_hour_are_refused(self):
        """Not rounded. Rounding a request nobody meant to make is worse than
        refusing it."""
        with self.assertRaises(ValueError):
            request_hours(
                LeaveRequestType.PAID,
                datetime.date(2026, 6, 18),
                datetime.date(2026, 6, 18),
                datetime.time(9, 10),
                datetime.time(13, 0),
                NO_HOLIDAYS,
            )

    def test_a_span_that_ends_before_it_starts_is_refused(self):
        with self.assertRaises(ValueError):
            request_hours(
                LeaveRequestType.PAID,
                datetime.date(2026, 6, 18),
                datetime.date(2026, 6, 18),
                datetime.time(13, 0),
                datetime.time(9, 0),
                NO_HOLIDAYS,
            )

    def test_a_span_longer_than_a_working_day_is_refused(self):
        with self.assertRaises(ValueError):
            request_hours(
                LeaveRequestType.PAID,
                datetime.date(2026, 6, 18),
                datetime.date(2026, 6, 18),
                datetime.time(8, 0),
                datetime.time(17, 0),
                NO_HOLIDAYS,
            )

    def test_sick_leave_is_measured_the_same_way(self):
        """Sick leave deducts nothing, but its hours decide whether a manager
        has to approve it, so they are counted identically."""
        hours = request_hours(
            LeaveRequestType.SICK,
            datetime.date(2026, 6, 18),
            datetime.date(2026, 6, 22),
            None,
            None,
            DRAGON_BOAT,
        )

        self.assertEqual(hours, Decimal("16.00"))


class TestExchangeHours(unittest.TestCase):
    def test_every_day_of_an_exchange_counts(self):
        """The opposite of leave. A range with an unexchangeable day in it
        cannot be submitted at all, so there is no day to skip -- and skipping
        one would mean somebody worked and was not credited."""
        hours = request_hours(
            LeaveRequestType.EXCHANGE,
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 3),
            None,
            None,
            frozenset({
                datetime.date(2026, 10, 1),
                datetime.date(2026, 10, 2),
                datetime.date(2026, 10, 3),
            }),
        )

        self.assertEqual(hours, Decimal("24.00"))

    def test_an_exchanged_day_that_is_also_a_weekend_still_counts(self):
        """They came in and worked it. 2026-10-03 is a Saturday and the 4th a
        Sunday; both are company holidays here."""
        hours = request_hours(
            LeaveRequestType.EXCHANGE,
            datetime.date(2026, 10, 3),
            datetime.date(2026, 10, 4),
            None,
            None,
            frozenset({datetime.date(2026, 10, 3), datetime.date(2026, 10, 4)}),
        )

        self.assertEqual(hours, Decimal("16.00"))

    def test_an_exchange_cannot_carry_times(self):
        """Half a day back at work is not on offer, and silently ignoring the
        times would credit a whole day for it."""
        with self.assertRaises(ValueError):
            request_hours(
                LeaveRequestType.EXCHANGE,
                datetime.date(2026, 10, 1),
                datetime.date(2026, 10, 1),
                datetime.time(9, 0),
                datetime.time(13, 0),
                frozenset({datetime.date(2026, 10, 1)}),
            )


class TestRequiredNotice(unittest.TestCase):
    def test_a_day_off_needs_two_working_days_of_notice(self):
        self.assertEqual(required_notice_workdays(Decimal("8.00")), 2)

    def test_part_of_a_day_counts_as_a_whole_one(self):
        """Rounded up to whole days first: four hours and eight ask the same."""
        self.assertEqual(required_notice_workdays(Decimal("4.00")), 2)
        self.assertEqual(required_notice_workdays(Decimal("0.50")), 2)

    def test_three_days_need_six(self):
        self.assertEqual(required_notice_workdays(Decimal("24.00")), 6)

    def test_nine_hours_are_two_days(self):
        self.assertEqual(required_notice_workdays(Decimal("9.00")), 4)


class TestWorkdaysBefore(unittest.TestCase):
    """The design's notice table, on its real dates. Leave starts Thursday
    13 August 2026 and runs three days, so it needs six working days. The 9th
    is a Sunday and the 10th a Monday."""

    def test_submitting_on_the_fifth_gives_six_working_days(self):
        self.assertEqual(
            workdays_before(
                datetime.date(2026, 8, 5), datetime.date(2026, 8, 13), NO_HOLIDAYS
            ),
            6,
        )

    def test_submitting_a_day_later_gives_five(self):
        self.assertEqual(
            workdays_before(
                datetime.date(2026, 8, 6), datetime.date(2026, 8, 13), NO_HOLIDAYS
            ),
            5,
        )

    def test_the_day_of_submission_counts_and_the_first_day_off_does_not(self):
        """Chosen deliberately, and it is what makes the 5th compliant above.
        Defining it the other way round would fail that row."""
        self.assertEqual(
            workdays_before(
                datetime.date(2026, 8, 11), datetime.date(2026, 8, 13), NO_HOLIDAYS
            ),
            2,
        )

    def test_asking_today_for_today_gives_nothing(self):
        """An empty range. Same-day leave is always late notice, which is the
        expected answer rather than an error."""
        self.assertEqual(
            workdays_before(
                datetime.date(2026, 8, 13), datetime.date(2026, 8, 13), NO_HOLIDAYS
            ),
            0,
        )

    def test_a_company_holiday_in_between_does_not_count_as_notice(self):
        """Same definition as the deduction: nobody is at work to arrange
        cover on a day the office is shut."""
        self.assertEqual(
            workdays_before(
                datetime.date(2026, 6, 18),
                datetime.date(2026, 6, 20),
                DRAGON_BOAT,
            ),
            1,
        )


class TestHoursByDay(unittest.TestCase):
    """The days a request covers, each with its hours. Their sum is what
    request_hours answers, so the two cannot drift apart."""

    def _split(
        self,
        request_type,
        start,
        end,
        start_time=None,
        end_time=None,
        holidays=NO_HOLIDAYS,
    ):
        days = hours_by_day(request_type, start, end, start_time, end_time, holidays)
        total = request_hours(request_type, start, end, start_time, end_time, holidays)
        self.assertEqual(sum((hours for _, hours in days), Decimal("0.00")), total)
        return days

    def test_a_range_across_new_year_lists_each_working_day(self):
        new_year = frozenset({datetime.date(2027, 1, 1)})

        days = self._split(
            LeaveRequestType.PAID,
            datetime.date(2026, 12, 30),
            datetime.date(2027, 1, 2),
            holidays=new_year,
        )

        self.assertEqual(
            days,
            [
                (datetime.date(2026, 12, 30), Decimal("8.00")),
                (datetime.date(2026, 12, 31), Decimal("8.00")),
                (datetime.date(2027, 1, 2), Decimal("8.00")),
            ],
        )

    def test_the_weekly_days_off_are_left_out(self):
        # Saturday 2026-06-13 to Tuesday 2026-06-16: Sunday and Monday are off.
        days = self._split(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 13),
            datetime.date(2026, 6, 16),
        )

        self.assertEqual(
            [day for day, _ in days],
            [datetime.date(2026, 6, 13), datetime.date(2026, 6, 16)],
        )

    def test_a_part_day_is_its_one_day_and_its_hours(self):
        days = self._split(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 18),
            datetime.date(2026, 6, 18),
            datetime.time(9, 0),
            datetime.time(12, 30),
        )

        self.assertEqual(days, [(datetime.date(2026, 6, 18), Decimal("3.50"))])

    def test_a_part_day_on_a_holiday_lists_nothing(self):
        days = self._split(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 19),
            datetime.date(2026, 6, 19),
            datetime.time(9, 0),
            datetime.time(12, 0),
            holidays=DRAGON_BOAT,
        )

        self.assertEqual(days, [])

    def test_an_exchange_lists_every_day_it_covers(self):
        days = self._split(
            LeaveRequestType.EXCHANGE,
            datetime.date(2026, 6, 19),
            datetime.date(2026, 6, 20),
            holidays=frozenset({
                datetime.date(2026, 6, 19),
                datetime.date(2026, 6, 20),
            }),
        )

        self.assertEqual(
            days,
            [
                (datetime.date(2026, 6, 19), Decimal("8.00")),
                (datetime.date(2026, 6, 20), Decimal("8.00")),
            ],
        )


class TestDaysNotCounted(unittest.TestCase):
    def test_a_range_lists_the_weekend_and_the_holiday_it_skips(self):
        """Thursday 6/18 to Tuesday 6/23: Friday is the Dragon Boat Festival,
        Sunday and Monday are the weekend. Three days counted, three skipped,
        and together they are the whole range."""
        skipped = days_not_counted(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 18),
            datetime.date(2026, 6, 23),
            None,
            None,
            DRAGON_BOAT,
        )

        self.assertEqual(
            skipped,
            [
                datetime.date(2026, 6, 19),
                datetime.date(2026, 6, 21),
                datetime.date(2026, 6, 22),
            ],
        )
        counted = hours_by_day(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 18),
            datetime.date(2026, 6, 23),
            None,
            None,
            DRAGON_BOAT,
        )
        self.assertEqual(len(counted) + len(skipped), 6)

    def test_sick_leave_skips_days_off_the_same_way(self):
        skipped = days_not_counted(
            LeaveRequestType.SICK,
            datetime.date(2026, 6, 20),
            datetime.date(2026, 6, 23),
            None,
            None,
            NO_HOLIDAYS,
        )

        self.assertEqual(
            skipped, [datetime.date(2026, 6, 21), datetime.date(2026, 6, 22)]
        )

    def test_a_range_of_working_days_skips_nothing(self):
        skipped = days_not_counted(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 16),
            datetime.date(2026, 6, 18),
            None,
            None,
            NO_HOLIDAYS,
        )

        self.assertEqual(skipped, [])

    def test_an_exchange_skips_nothing(self):
        """An exchange counts every day it covers."""
        skipped = days_not_counted(
            LeaveRequestType.EXCHANGE,
            datetime.date(2026, 6, 19),
            datetime.date(2026, 6, 19),
            None,
            None,
            DRAGON_BOAT,
        )

        self.assertEqual(skipped, [])

    def test_a_part_day_skips_nothing(self):
        skipped = days_not_counted(
            LeaveRequestType.PAID,
            datetime.date(2026, 6, 16),
            datetime.date(2026, 6, 16),
            datetime.time(9, 0),
            datetime.time(12, 0),
            NO_HOLIDAYS,
        )

        self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
