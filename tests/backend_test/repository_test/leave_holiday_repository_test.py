"""Reads and the whole-year replacement behind the company holiday calendar."""

import datetime

from backend.entity.leave_holiday_entity import LeaveHolidayEntity
from backend.repository.leave_holiday_repository import LeaveHolidayRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _row(day, name="Spring Festival", is_exchangeable=False):
    return LeaveHolidayEntity(
        year=day.year, date=day, name=name, is_exchangeable=is_exchangeable
    )


class TestLeaveHolidayRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repository = LeaveHolidayRepository()

    async def test_a_year_comes_back_ascending_by_date(self):
        """Grouping rows into segments walks them in order, so the order is
        this query's responsibility rather than the caller's."""
        await self.insert_entities([
            _row(datetime.date(2026, 5, 1)),
            _row(datetime.date(2026, 1, 1)),
            _row(datetime.date(2026, 2, 17)),
        ])

        rows = await self.repository.list_by_year(self.session, 2026)

        self.assertEqual(
            [row.date for row in rows],
            [
                datetime.date(2026, 1, 1),
                datetime.date(2026, 2, 17),
                datetime.date(2026, 5, 1),
            ],
        )

    async def test_only_the_year_asked_for_comes_back(self):
        await self.insert_entities([
            _row(datetime.date(2025, 10, 1)),
            _row(datetime.date(2026, 10, 1)),
            _row(datetime.date(2027, 10, 1)),
        ])

        rows = await self.repository.list_by_year(self.session, 2026)

        self.assertEqual([row.date.year for row in rows], [2026])

    async def test_replacing_a_year_leaves_exactly_the_rows_given(self):
        """Not a merge: whatever is absent from the new list is gone. Five days
        replaced by three has to end at three, or a shortened holiday keeps its
        old tail."""
        await self.insert_entities([
            _row(datetime.date(2026, 2, day)) for day in range(17, 22)
        ])

        await self.repository.replace_year(
            self.session,
            2026,
            [
                _row(datetime.date(2026, 2, day), name="Spring Festival")
                for day in (17, 18, 19)
            ],
        )
        rows = await self.repository.list_by_year(self.session, 2026)

        self.assertEqual(
            [row.date for row in rows],
            [
                datetime.date(2026, 2, 17),
                datetime.date(2026, 2, 18),
                datetime.date(2026, 2, 19),
            ],
        )

    async def test_replacing_one_year_does_not_touch_another(self):
        await self.insert_entities([
            _row(datetime.date(2025, 10, 1), name="National Day"),
            _row(datetime.date(2026, 10, 1), name="National Day"),
        ])

        await self.repository.replace_year(
            self.session, 2026, [_row(datetime.date(2026, 1, 1), name="New Year")]
        )
        rows = await self.repository.list_by_year(self.session, 2025)

        self.assertEqual([row.date for row in rows], [datetime.date(2025, 10, 1)])

    async def test_replacing_an_empty_year_just_inserts(self):
        await self.repository.replace_year(
            self.session, 2026, [_row(datetime.date(2026, 1, 1), name="New Year")]
        )

        rows = await self.repository.list_by_year(self.session, 2026)

        self.assertEqual(len(rows), 1)

    async def test_the_entered_years_come_back_once_each_ascending(self):
        """This drives the page's "nothing entered for next year" warning, so a
        year appearing once per row would make it useless."""
        await self.insert_entities([
            _row(datetime.date(2027, 1, 1), name="New Year"),
            _row(datetime.date(2026, 1, 1), name="New Year"),
            _row(datetime.date(2026, 5, 1), name="Labour Day"),
        ])

        years = await self.repository.list_years(self.session)

        self.assertEqual(years, [2026, 2027])


if __name__ == "__main__":
    import unittest

    unittest.main()
