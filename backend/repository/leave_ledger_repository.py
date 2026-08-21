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
          an exchange credit, a deduction, a reversal and a forfeit are all
          balance rather than entitlement. Counting an opening balance here
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

    async def latest_level_change_date(
        self, session: AsyncSession, user_id: int
    ) -> datetime.date | None:
        """The date this person's annual entitlement last changed.

        Args:
            session: Active async session.
            user_id: Whose ledger.

        Returns:
            The most recent ``level_change`` date, or None when there is none
            -- almost everybody. The arithmetic reads None as "the whole year
            at the current entitlement", which is the plain formula.
        """
        result = await session.execute(
            select(func.max(LeaveLedgerEntity.effective_date)).where(
                LeaveLedgerEntity.user_id == user_id,
                LeaveLedgerEntity.entry_type == LeaveEntryType.LEVEL_CHANGE,
            )
        )
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
