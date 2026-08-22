"""Company holiday calendar reads and the whole-year write."""

import datetime
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock, patch

from backend.dto.leave_holiday_dto import LeaveHolidaySegmentInputDto
from backend.entity.leave_holiday_entity import LeaveHolidayEntity
from backend.leave.leave_calendar_service import LeaveCalendarService


def _row(day, name="Spring Festival", is_exchangeable=False):
    return LeaveHolidayEntity(
        year=day.year, date=day, name=name, is_exchangeable=is_exchangeable
    )


def _segment(start, end, name="Spring Festival", is_exchangeable=False):
    return LeaveHolidaySegmentInputDto(
        name=name, start_date=start, end_date=end, is_exchangeable=is_exchangeable
    )


class LeaveCalendarServiceTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.repository = MagicMock()
        self.repository.list_by_year = AsyncMock(return_value=[])
        self.repository.list_years = AsyncMock(return_value=[])
        self.repository.replace_year = AsyncMock()
        self.session = MagicMock()
        self.session.commit = AsyncMock()
        self.service = LeaveCalendarService(
            logger=self.logger, leave_holiday_repository=self.repository
        )

    async def test_a_year_is_returned_as_segments_with_a_day_total(self):
        self.repository.list_by_year.return_value = [
            _row(datetime.date(2026, 2, 17)),
            _row(datetime.date(2026, 2, 18)),
            _row(datetime.date(2026, 5, 1), name="Labour Day"),
        ]

        year = await self.service.get_year(self.session, 2026)

        self.assertEqual(year.year, 2026)
        self.assertEqual([segment.day_count for segment in year.segments], [2, 1])
        self.assertEqual(year.total_days, 3)

    async def test_a_year_nobody_has_entered_reads_as_empty_rather_than_missing(self):
        """The page asks for a year before knowing whether it holds anything;
        the "not entered" warning comes from the years endpoint. A 404 here
        would only add an error branch that means the same thing."""
        year = await self.service.get_year(self.session, 2030)

        self.assertEqual(year.segments, [])
        self.assertEqual(year.total_days, 0)

    @patch("backend.leave.leave_calendar_service.business_today")
    async def test_this_year_and_next_come_from_the_beijing_day(self, business_today):
        """A browser in another timezone must not disagree about which year it
        is, and the server itself runs on UTC -- during the Beijing morning the
        two dates differ."""
        business_today.return_value = datetime.date(2026, 1, 1)
        self.repository.list_years.return_value = [2025, 2026]

        years = await self.service.list_years(self.session)

        self.assertEqual(years.current_year, 2026)
        self.assertEqual(years.next_year, 2027)
        self.assertEqual(years.years, [2025, 2026])

    async def test_replacing_a_year_writes_the_expanded_rows_and_commits(self):
        """The session does not commit on its own, so a missing commit here
        returns 200 with nothing stored -- a failure that raises nothing."""
        self.repository.list_by_year.return_value = [
            _row(datetime.date(2026, 2, 17)),
            _row(datetime.date(2026, 2, 18)),
        ]

        result = await self.service.replace_year(
            self.session,
            2026,
            [_segment(datetime.date(2026, 2, 17), datetime.date(2026, 2, 18))],
        )

        written = self.repository.replace_year.await_args.args[2]
        self.assertEqual(
            [row.date for row in written],
            [datetime.date(2026, 2, 17), datetime.date(2026, 2, 18)],
        )
        self.session.commit.assert_awaited_once()
        self.assertEqual(result.total_days, 2)

    async def test_what_comes_back_is_read_from_storage_not_from_the_request(self):
        """Read back after writing, so the admin sees what was actually stored
        -- which is how a mistyped date shows up as a segment that split."""
        self.repository.list_by_year.return_value = [
            _row(datetime.date(2026, 2, 17)),
            _row(datetime.date(2026, 2, 19)),
        ]

        result = await self.service.replace_year(
            self.session,
            2026,
            [_segment(datetime.date(2026, 2, 17), datetime.date(2026, 2, 19))],
        )

        self.assertEqual(len(result.segments), 2)

    async def test_an_invalid_year_writes_nothing_at_all(self):
        with self.assertRaises(ValueError):
            await self.service.replace_year(
                self.session,
                2026,
                [_segment(datetime.date(2026, 2, 19), datetime.date(2026, 2, 17))],
            )

        self.repository.replace_year.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_clearing_a_year_is_refused_before_anything_is_deleted(self):
        """An empty list would refuse every leave request dated in that year,
        and the delete runs before the insert -- so this has to be caught
        before the repository is touched, not by it."""
        with self.assertRaises(ValueError):
            await self.service.replace_year(self.session, 2026, [])

        self.repository.replace_year.assert_not_awaited()

    def test_the_policy_view_carries_the_weekend_and_the_ceilings(self):
        policy = self.service.get_policy()

        self.assertEqual(policy.weekend_labels, ["Sunday", "Monday"])
        self.assertEqual(policy.hours_per_day, 8)
        self.assertIsNone(policy.max_carryover_hours)


if __name__ == "__main__":
    main()
