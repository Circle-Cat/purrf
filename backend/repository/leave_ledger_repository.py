import datetime
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.leave_enums import LeaveEntryType
from backend.entity.leave_ledger_entity import LeaveLedgerEntity


class LeaveLedgerRepository:
    """Reads and writes over the append-only leave ledger.

    Nothing here commits: a job writes for many people, and either the whole
    run lands or none of it does.

    Every read is a sum whose filters are silent when they are wrong, so each
    one says on itself what it must and must not count.
    """

    async def sum_weekly_accrual(
        self,
        session: AsyncSession,
        user_id: int,
        year: int,
        before: datetime.date | None = None,
    ) -> Decimal:
        """What the accrual engine has already granted this person this year.

        Two filters, both essential and both quiet when dropped:

        * **``weekly_accrual`` only.** An opening balance, a manual correction,
          an exchange credit, a deduction and a forfeit are all balance
          rather than entitlement. Counting an opening balance here
          would cancel out the accrual it was keyed in alongside.
        * **Rows dated inside ``year`` only.** The target resets every January
          while the ledger keeps accumulating, so a sum taken across years
          measures this January's target against last year's whole entitlement,
          goes negative, pays nothing, and reports nothing -- for the rest of
          that year, with the gap doubling the year after.

        Args:
            session: Active async session.
            user_id: Whose ledger.
            year: The year being accrued for.
            before: Optional cut, exclusive. Used to total the part of the year
                that came before a level change; a row dated on the day of the
                change belongs to the new level.

        Returns:
            Hours, or ``0.00`` when there are none -- never None, since the
            arithmetic subtracts this from a target.
        """
        query = select(
            func.coalesce(func.sum(LeaveLedgerEntity.hours), Decimal("0.00"))
        ).where(
            LeaveLedgerEntity.user_id == user_id,
            LeaveLedgerEntity.entry_type == LeaveEntryType.WEEKLY_ACCRUAL,
            extract("year", LeaveLedgerEntity.effective_date) == year,
        )
        if before is not None:
            query = query.where(LeaveLedgerEntity.effective_date < before)
        result = await session.execute(query)
        return result.scalar_one()

    async def sum_deductions_for_year(
        self, session: AsyncSession, user_id: int, year: int
    ) -> Decimal:
        """What leave this person has actually spent inside one year.

        Deductions only, and dated inside the year. Both filters matter for the
        same reason the accrual sum needs them: an exchange credit and an
        opening balance are not leave taken, and a figure summed across years
        would say somebody spent this year what they spent over their whole
        employment.

        Returned as stored, which is negative or zero. The caller decides how
        to present it -- negating here would hide the sign from a reader of the
        query and invite a second negation somewhere else.

        Args:
            session: Active async session.
            user_id: Whose ledger.
            year: The year to total.

        Returns:
            The signed sum, or ``0.00`` when there are none.
        """
        result = await session.execute(
            select(
                func.coalesce(func.sum(LeaveLedgerEntity.hours), Decimal("0.00"))
            ).where(
                LeaveLedgerEntity.user_id == user_id,
                LeaveLedgerEntity.entry_type == LeaveEntryType.LEAVE_DEDUCTION,
                extract("year", LeaveLedgerEntity.effective_date) == year,
            )
        )
        return result.scalar_one()

    async def balance(self, session: AsyncSession, user_id: int) -> Decimal:
        """This person's balance: every row they have, whatever its type.

        Deliberately unfiltered. There is no balance column and no second
        source of truth, so excluding a type here would make the number
        disagree with the history it is derived from. It is also why a level
        change carries no hours -- a marker that moved the balance would force
        every caller of this to remember an exclusion.

        A negative result is ordinary: an L1 has no annual entitlement and may
        still take paid leave.

        Args:
            session: Active async session.
            user_id: Whose ledger.

        Returns:
            The signed sum, or ``0.00`` for an empty ledger.
        """
        result = await session.execute(
            select(
                func.coalesce(func.sum(LeaveLedgerEntity.hours), Decimal("0.00"))
            ).where(LeaveLedgerEntity.user_id == user_id)
        )
        return result.scalar_one()

    async def balances_by_user_ids(
        self, session: AsyncSession, user_ids: list[int]
    ) -> dict[int, Decimal]:
        """Balances for several people at once, one read.

        Same rule as :meth:`balance` -- every row, whatever its type -- but for
        a whole queue. An approver's list needs one per row, and a query per row
        would grow with the queue.

        Somebody with no ledger rows is left out of the map rather than given a
        zero: absent and zero are different questions, and only the caller knows
        which answer it wants.

        Args:
            session: Active async session.
            user_ids: Whose balances. An empty list short-circuits.

        Returns:
            ``{user_id: balance}`` for the people who have rows.
        """
        if not user_ids:
            return {}
        result = await session.execute(
            select(
                LeaveLedgerEntity.user_id,
                func.coalesce(func.sum(LeaveLedgerEntity.hours), Decimal("0.00")),
            )
            .where(LeaveLedgerEntity.user_id.in_(user_ids))
            .group_by(LeaveLedgerEntity.user_id)
        )
        return {user_id: total for user_id, total in result.all()}

    async def latest_level_change_date(
        self,
        session: AsyncSession,
        user_id: int,
        on_or_before: datetime.date | None = None,
    ) -> datetime.date | None:
        """The date this person's annual entitlement last changed.

        Args:
            session: Active async session.
            user_id: Whose ledger.
            on_or_before: Latest date to consider, inclusive. The annual job
                closes out the previous year and passes its 31 December: a
                change made after that year ended would otherwise split the
                closing year at a date outside it and pay the wrong
                proportion.

        Returns:
            The most recent ``level_change`` date, or None when there is none
            -- almost everybody. The arithmetic reads None as "the whole year
            at the current entitlement", which is the plain formula.
        """
        query = select(func.max(LeaveLedgerEntity.effective_date)).where(
            LeaveLedgerEntity.user_id == user_id,
            LeaveLedgerEntity.entry_type == LeaveEntryType.LEVEL_CHANGE,
        )
        if on_or_before is not None:
            query = query.where(LeaveLedgerEntity.effective_date <= on_or_before)
        result = await session.execute(query)
        return result.scalar_one()

    async def add_entries(
        self, session: AsyncSession, entries: list[LeaveLedgerEntity]
    ) -> None:
        """Appends ledger rows. Never updates or deletes one.

        Flushes so that the partial unique index speaks now rather than at
        commit: a retried job hitting the same person and date raises here
        instead of appearing to succeed.

        Args:
            session: Active async session. Not committed.
            entries: Rows to append.
        """
        session.add_all(entries)
        await session.flush()
