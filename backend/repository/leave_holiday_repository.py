from sqlalchemy import delete, distinct, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.leave_holiday_entity import LeaveHolidayEntity

# The first half of the advisory lock key a year's replacement takes; the second
# half is the year. Any fixed int4 will do as long as nothing else in the
# database uses it.
_YEAR_LOCK_NAMESPACE = 0x4C484F4C  # "LHOL"


class LeaveHolidayRepository:
    """Company holiday rows, read and written a whole year at a time.

    A segment on the calendar page has no identity of its own, so there is
    nothing to address with a partial update: the write path replaces a year.
    That also makes it idempotent, which matters more than it sounds -- an
    admin enters a year once and a retried request must not double it.

    Nothing here commits. The service owns the transaction boundary, so the
    delete and the insert that follows it either both land or neither does.
    """

    async def list_by_year(
        self, session: AsyncSession, year: int
    ) -> list[LeaveHolidayEntity]:
        """Every row of one year, ascending by date.

        The order is part of the contract: grouping rows into segments walks
        them in sequence and would split a run that arrived shuffled.

        Args:
            session: Active async session.
            year: The year to read.

        Returns:
            That year's rows, oldest first.
        """
        result = await session.execute(
            select(LeaveHolidayEntity)
            .where(LeaveHolidayEntity.year == year)
            .order_by(LeaveHolidayEntity.date)
        )
        return list(result.scalars().all())

    async def list_years(self, session: AsyncSession) -> list[int]:
        """The years that hold at least one row, ascending.

        Drives the "nothing entered for next year" warning, which is why it is
        a distinct query on ``year`` -- the leading column of the unique
        constraint -- rather than a scan of dates.

        Args:
            session: Active async session.

        Returns:
            Each entered year once, in order.
        """
        result = await session.execute(
            select(distinct(LeaveHolidayEntity.year)).order_by(LeaveHolidayEntity.year)
        )
        return list(result.scalars().all())

    async def replace_year(
        self,
        session: AsyncSession,
        year: int,
        holidays: list[LeaveHolidayEntity],
    ) -> None:
        """Deletes the year and writes the rows given, in one transaction.

        A replacement, not a merge: a day absent from ``holidays`` is gone, so
        shortening a holiday actually shortens it instead of leaving its old
        tail behind.

        Two saves of one year queue on a lock held until the transaction ends.
        Without it the second delete waits on the rows the first deleted, then
        cannot see the rows the first inserted, so it removes nothing: its
        insert either collides with the first save's dates or merges with them.
        Queued, the later save replaces the earlier one.

        Args:
            session: Active async session. Not committed here.
            year: The year being replaced.
            holidays: Its complete set of rows.
        """
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, :year)"),
            {"namespace": _YEAR_LOCK_NAMESPACE, "year": year},
        )
        await session.execute(
            delete(LeaveHolidayEntity).where(LeaveHolidayEntity.year == year)
        )
        session.add_all(holidays)
        await session.flush()
