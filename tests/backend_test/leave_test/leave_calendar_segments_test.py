"""Grouping rows into segments, and expanding segments back into rows.

Storage is one row per day; the calendar page enters and reads back whole
segments. Neither direction is allowed to hide a mistyped date, which is what
most of these cases are about.
"""

import datetime
import unittest

from backend.dto.leave_holiday_dto import LeaveHolidaySegmentInputDto
from backend.entity.leave_holiday_entity import LeaveHolidayEntity
from backend.leave.leave_calendar_segments import expand_segments, group_into_segments


def _row(day, name, is_exchangeable=False, year=2026):
    return LeaveHolidayEntity(
        year=year, date=day, name=name, is_exchangeable=is_exchangeable
    )


def _segment(start, end, name="Spring Festival", is_exchangeable=False):
    return LeaveHolidaySegmentInputDto(
        name=name, start_date=start, end_date=end, is_exchangeable=is_exchangeable
    )


class TestGroupIntoSegments(unittest.TestCase):
    def test_consecutive_days_under_one_name_are_one_segment(self):
        rows = [
            _row(datetime.date(2026, 2, 17), "Spring Festival"),
            _row(datetime.date(2026, 2, 18), "Spring Festival"),
            _row(datetime.date(2026, 2, 19), "Spring Festival"),
        ]

        segments = group_into_segments(rows)

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].start_date, datetime.date(2026, 2, 17))
        self.assertEqual(segments[0].end_date, datetime.date(2026, 2, 19))
        self.assertEqual(segments[0].day_count, 3)

    def test_a_gap_of_one_day_splits_the_segment(self):
        """A holiday entered with one date mistyped shows up as two segments
        rather than as one that silently spans the gap."""
        rows = [
            _row(datetime.date(2026, 2, 17), "Spring Festival"),
            _row(datetime.date(2026, 2, 19), "Spring Festival"),
        ]

        segments = group_into_segments(rows)

        self.assertEqual(len(segments), 2)
        self.assertEqual(
            [segment.day_count for segment in segments],
            [1, 1],
        )

    def test_consecutive_days_under_different_names_are_two_segments(self):
        rows = [
            _row(datetime.date(2026, 10, 1), "National Day"),
            _row(datetime.date(2026, 10, 2), "Mid-Autumn Festival"),
        ]

        segments = group_into_segments(rows)

        self.assertEqual(
            [segment.name for segment in segments],
            ["National Day", "Mid-Autumn Festival"],
        )

    def test_consecutive_days_that_disagree_on_exchangeable_are_two_segments(self):
        """Entry sets one flag for a whole segment, so a split here can only
        come from hand-written SQL. Showing it as two segments makes the
        inconsistency visible instead of taking the first row's value."""
        rows = [
            _row(datetime.date(2026, 5, 1), "Labour Day", is_exchangeable=True),
            _row(datetime.date(2026, 5, 2), "Labour Day", is_exchangeable=False),
        ]

        segments = group_into_segments(rows)

        self.assertEqual(len(segments), 2)
        self.assertEqual(
            [segment.is_exchangeable for segment in segments], [True, False]
        )

    def test_a_single_day_is_a_segment_of_one(self):
        segments = group_into_segments([_row(datetime.date(2026, 1, 1), "New Year")])

        self.assertEqual(segments[0].start_date, segments[0].end_date)
        self.assertEqual(segments[0].day_count, 1)

    def test_a_year_with_no_rows_has_no_segments(self):
        self.assertEqual(group_into_segments([]), [])


class TestExpandSegments(unittest.TestCase):
    def test_a_segment_becomes_one_row_per_day(self):
        rows = expand_segments(
            2026, [_segment(datetime.date(2026, 2, 17), datetime.date(2026, 2, 19))]
        )

        self.assertEqual(
            [row.date for row in rows],
            [
                datetime.date(2026, 2, 17),
                datetime.date(2026, 2, 18),
                datetime.date(2026, 2, 19),
            ],
        )
        self.assertEqual({row.year for row in rows}, {2026})

    def test_the_segment_flag_lands_on_every_row_it_expands_to(self):
        rows = expand_segments(
            2026,
            [
                _segment(
                    datetime.date(2026, 5, 1),
                    datetime.date(2026, 5, 3),
                    is_exchangeable=True,
                )
            ],
        )

        self.assertEqual([row.is_exchangeable for row in rows], [True, True, True])

    def test_the_stored_name_is_stripped(self):
        rows = expand_segments(
            2026,
            [
                _segment(
                    datetime.date(2026, 1, 1),
                    datetime.date(2026, 1, 1),
                    name="  New Year  ",
                )
            ],
        )

        self.assertEqual(rows[0].name, "New Year")

    def test_expanding_and_grouping_are_inverses(self):
        segments = [
            _segment(datetime.date(2026, 2, 17), datetime.date(2026, 2, 19)),
            _segment(
                datetime.date(2026, 5, 1),
                datetime.date(2026, 5, 3),
                name="Labour Day",
                is_exchangeable=True,
            ),
        ]

        regrouped = group_into_segments(expand_segments(2026, segments))

        self.assertEqual(
            [(s.name, s.start_date, s.end_date, s.is_exchangeable) for s in regrouped],
            [
                (
                    "Spring Festival",
                    datetime.date(2026, 2, 17),
                    datetime.date(2026, 2, 19),
                    False,
                ),
                (
                    "Labour Day",
                    datetime.date(2026, 5, 1),
                    datetime.date(2026, 5, 3),
                    True,
                ),
            ],
        )


class TestExpandSegmentsRejects(unittest.TestCase):
    """The five checks all raise ValueError, which the global handler turns
    into a 400. Letting a database constraint report these instead would show
    an admin a raw Postgres error, or write rows that silently disappear."""

    def test_a_date_outside_the_year_being_replaced(self):
        with self.assertRaises(ValueError):
            expand_segments(
                2026,
                [_segment(datetime.date(2025, 12, 30), datetime.date(2025, 12, 31))],
            )

    def test_a_segment_spanning_two_years_says_to_split_it(self):
        """One row belongs to one year and the endpoint replaces one year, so
        New Year has to be entered as two segments. The message has to say so
        -- the admin picked a range the calendar cannot hold."""
        with self.assertRaises(ValueError) as caught:
            expand_segments(
                2026,
                [_segment(datetime.date(2026, 12, 30), datetime.date(2027, 1, 2))],
            )

        self.assertIn("two segments", str(caught.exception))

    def test_two_segments_claiming_the_same_day(self):
        with self.assertRaises(ValueError):
            expand_segments(
                2026,
                [
                    _segment(datetime.date(2026, 2, 17), datetime.date(2026, 2, 19)),
                    _segment(
                        datetime.date(2026, 2, 19),
                        datetime.date(2026, 2, 20),
                        name="Spring Festival week 2",
                    ),
                ],
            )

    def test_a_segment_that_ends_before_it_starts(self):
        """Without this the segment expands to no rows at all and those days
        vanish without a word."""
        with self.assertRaises(ValueError):
            expand_segments(
                2026,
                [_segment(datetime.date(2026, 2, 19), datetime.date(2026, 2, 17))],
            )

    def test_a_name_that_is_only_whitespace(self):
        with self.assertRaises(ValueError):
            expand_segments(
                2026,
                [
                    _segment(
                        datetime.date(2026, 2, 17),
                        datetime.date(2026, 2, 17),
                        name="   ",
                    )
                ],
            )

    def test_an_empty_segment_list(self):
        """Clearing a year is not an edit, it is switching leave off for that
        year: with no rows, every submission for it is refused."""
        with self.assertRaises(ValueError):
            expand_segments(2026, [])


if __name__ == "__main__":
    unittest.main()
