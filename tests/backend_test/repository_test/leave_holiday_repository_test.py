"""Reads and the whole-year replacement behind the company holiday calendar."""

import datetime
from unittest.mock import patch

from sqlalchemy import text

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


class TestReplaceYearLock(BaseRepositoryTestLib):
    """Two saves of one year have to queue.

    Unlocked, the second delete cannot see the rows the first save inserted,
    so it removes nothing and its insert collides or merges. A missing lock is
    invisible to every test that saves once, so the lock itself is asserted.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repository = LeaveHolidayRepository()

    async def _held_advisory_locks(self):
        rows = await self.session.execute(
            text(
                "SELECT classid, objid FROM pg_locks "
                "WHERE locktype = 'advisory' AND pid = pg_backend_pid() AND granted"
            )
        )
        return {(int(classid), int(objid)) for classid, objid in rows.all()}

    async def test_only_the_year_being_saved_is_locked(self):
        await self.repository.replace_year(
            self.session, 2027, [_row(datetime.date(2027, 1, 1), name="New Year")]
        )

        held = await self._held_advisory_locks()
        self.assertIn((0x4C484F4C, 2027), held)
        self.assertNotIn((0x4C484F4C, 2026), held)

    async def test_the_lock_is_taken_before_the_year_is_deleted(self):
        """Taken after the delete, the delete has already chosen what it
        removes and the race is back."""
        with patch.object(
            self.session, "execute", wraps=self.session.execute
        ) as execute:
            await self.repository.replace_year(
                self.session,
                2027,
                [_row(datetime.date(2027, 1, 1), name="New Year")],
            )

        statements = [str(call.args[0]) for call in execute.call_args_list]
        self.assertIn("pg_advisory_xact_lock", statements[0])
        self.assertTrue(statements[1].startswith("DELETE FROM leave_holiday"))


if __name__ == "__main__":
    import unittest

    unittest.main()
