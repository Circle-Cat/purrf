import datetime
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import case, extract, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.leave_enums import LeaveEntryType
from backend.entity.leave_ledger_entity import LeaveLedgerEntity

# The advisory lock key the two scheduled leave jobs share. Any fixed pair of
# int4s will do as long as nothing else in the database uses it.
_JOB_LOCK_NAMESPACE = 0x4C4A4F42  # "LJOB"
_JOB_LOCK_KEY = 0


@dataclass(frozen=True)
class LedgerLine:
    """One line of a ledger listing.

    A request's days are stored as a row each and read back as one line: hours
    summed, dated from its first day to its last. Every other row is a line of
    its own, with ``end_date`` equal to ``effective_date``.
    """

    leave_ledger_id: int
    user_id: int
    entry_type: LeaveEntryType
    hours: Decimal
    effective_date: datetime.date
    end_date: datetime.date
    note: str | None


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

    async def balance(
        self,
        session: AsyncSession,
        user_id: int,
        *,
        on_or_before: datetime.date | None = None,
    ) -> Decimal:
        """This person's balance: every row they have, whatever its type.

        Never filtered by type. There is no balance column and no second source
        of truth, so excluding a type here would make the number disagree with
        the history it is derived from. It is also why a level change carries
        no hours -- a marker that moved the balance would force every caller of
        this to remember an exclusion.

        ``on_or_before`` is a different axis, and the only caller that needs it
        is the carryover trim: what it cuts is the overshoot a year ended with,
        so it has to ask what the balance was on 31 December rather than what
        it is now. Two rows can already sit between the two answers by the time
        the close runs -- the new year's first weekly accrual, and leave
        approved in December for a January date -- and the cut is irreversible.

        A negative result is ordinary: an L1 has no annual entitlement and may
        still take paid leave.

        Args:
            session: Active async session.
            user_id: Whose ledger.
            on_or_before: Count only rows effective on or before this date.
                Defaults to counting everything, which is the balance now.

        Returns:
            The signed sum, or ``0.00`` for an empty ledger.
        """
        stmt = select(
            func.coalesce(func.sum(LeaveLedgerEntity.hours), Decimal("0.00"))
        ).where(LeaveLedgerEntity.user_id == user_id)
        if on_or_before is not None:
            stmt = stmt.where(LeaveLedgerEntity.effective_date <= on_or_before)
        result = await session.execute(stmt)
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

    async def list_level_changes(
        self, session: AsyncSession, user_id: int
    ) -> list[LeaveLedgerEntity]:
        """Every entitlement change on record for this person, oldest first.

        Not bounded by year on purpose. A change before the year says what it
        started at, and one after it says what it ended at -- which is what a
        settlement run after a 1 January promotion has to read, rather than the
        level as it stands now.

        Args:
            session: Active async session.
            user_id: Whose ledger.

        Returns:
            The ``level_change`` rows by date, and in the order they were written
            within one date, since a level raised and put back on one day ends
            where it was put. Empty for almost everybody.
        """
        result = await session.execute(
            select(LeaveLedgerEntity)
            .where(
                LeaveLedgerEntity.user_id == user_id,
                LeaveLedgerEntity.entry_type == LeaveEntryType.LEVEL_CHANGE,
            )
            .order_by(
                LeaveLedgerEntity.effective_date, LeaveLedgerEntity.leave_ledger_id
            )
        )
        return list(result.scalars().all())

    async def lock_jobs(self, session: AsyncSession) -> None:
        """Holds the scheduled jobs' lock until the transaction ends.

        Each job pays the difference between what is owed and what the ledger
        already holds. Two runs at once would both read the same holding and
        both pay the difference; queued, the second reads the first's rows and
        pays only what is still owed. The weekly accrual and the annual close
        share the one lock, since both write the year's accrual.

        Args:
            session: Active async session.
        """
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, :key)"),
            {"namespace": _JOB_LOCK_NAMESPACE, "key": _JOB_LOCK_KEY},
        )

    async def add_entries(
        self, session: AsyncSession, entries: list[LeaveLedgerEntity]
    ) -> None:
        """Appends ledger rows. Never updates or deletes one.

        Args:
            session: Active async session. Not committed.
            entries: Rows to append.
        """
        session.add_all(entries)
        await session.flush()

    async def get_by_id(
        self, session: AsyncSession, leave_ledger_id: int
    ) -> LeaveLedgerEntity | None:
        """One ledger row, or None when there is no such row.

        Args:
            session: Active async session.
            leave_ledger_id: The row's id.

        Returns:
            The row, or None.
        """
        return await session.get(LeaveLedgerEntity, leave_ledger_id)

    @staticmethod
    def _line_key():
        """Rows of one request share a line; any other row is a line alone."""
        return case(
            (
                LeaveLedgerEntity.source_request_id.is_not(None),
                -LeaveLedgerEntity.source_request_id,
            ),
            else_=LeaveLedgerEntity.leave_ledger_id,
        )

    async def list_lines(
        self,
        session: AsyncSession,
        user_id: int | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[LedgerLine]:
        """The ledger as people read it, newest first, one line per request.

        Merged here rather than by the caller so a page never splits a
        request's days and the count beside it agrees with what is shown.

        Args:
            session: Active async session.
            user_id: Whose lines. None lists everybody's.
            limit: Lines per page. None returns them all.
            offset: Lines to skip.

        Returns:
            Lines ordered by their first day, then by their first row, both
            descending.
        """
        key = self._line_key()
        stmt = select(
            func.min(LeaveLedgerEntity.leave_ledger_id).label("leave_ledger_id"),
            LeaveLedgerEntity.user_id,
            LeaveLedgerEntity.entry_type,
            func.sum(LeaveLedgerEntity.hours).label("hours"),
            func.min(LeaveLedgerEntity.effective_date).label("effective_date"),
            func.max(LeaveLedgerEntity.effective_date).label("end_date"),
            func.max(LeaveLedgerEntity.note).label("note"),
        )
        if user_id is not None:
            stmt = stmt.where(LeaveLedgerEntity.user_id == user_id)
        stmt = (
            stmt.group_by(key, LeaveLedgerEntity.user_id, LeaveLedgerEntity.entry_type)
            .order_by(
                func.min(LeaveLedgerEntity.effective_date).desc(),
                func.min(LeaveLedgerEntity.leave_ledger_id).desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return [LedgerLine(**row._mapping) for row in result.all()]

    async def list_user_ids(self, session: AsyncSession) -> list[int]:
        """Everyone with at least one ledger row, whatever they are now.

        Wider than the people the engine pays: somebody who has left, or is no
        longer internal, keeps the history they built up and an admin still
        needs to read it.

        Args:
            session: Active async session.

        Returns:
            Their user ids, ascending.
        """
        result = await session.execute(
            select(LeaveLedgerEntity.user_id)
            .distinct()
            .order_by(LeaveLedgerEntity.user_id)
        )
        return list(result.scalars().all())

    async def count_lines(
        self, session: AsyncSession, user_id: int | None = None
    ) -> int:
        """How many lines :meth:`list_lines` would return without a limit.

        Args:
            session: Active async session.
            user_id: Whose lines. None counts everybody's.

        Returns:
            The number of lines.
        """
        stmt = select(self._line_key().label("line")).distinct()
        if user_id is not None:
            stmt = stmt.where(LeaveLedgerEntity.user_id == user_id)
        result = await session.execute(
            select(func.count()).select_from(stmt.subquery())
        )
        return result.scalar_one()
