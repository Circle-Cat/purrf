"""Hand-written ledger corrections."""

import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.leave_enums import LeaveEntryType
from backend.dto.leave_adjustment_dto import LeaveAdjustmentResultDto
from backend.entity.leave_ledger_entity import LeaveLedgerEntity
from backend.leave.leave_accrual import NO_HOURS, format_hours
from backend.leave.leave_clock import business_today


class LeaveAdjustmentService:
    """Adjusts one person's balance by hand, for a stated reason.

    Two jobs at launch, both the same entry type. The balance carried in from
    the previous year arrives as a positive correction dated 31 December; leave
    already taken this year arrives as negative hours, because a request cannot
    be dated in the past. Which one a row is lives in its note.

    Corrections are deliberately outside the ledger's double-write index: an
    admin may legitimately book several for one person on one day. Nothing here
    dedupes, so a form that submits twice writes twice -- the balance returned
    is what an admin checks against.
    """

    def __init__(self, logger, leave_ledger_repository, users_repository):
        """
        Args:
            logger: Structured logger.
            leave_ledger_repository (LeaveLedgerRepository): Ledger rows.
            users_repository (UsersRepository): Existence check for the target.
        """
        self.logger = logger
        self.leave_ledger_repository = leave_ledger_repository
        self.users_repository = users_repository

    async def adjust(
        self,
        session: AsyncSession,
        user_id: int,
        hours: Decimal,
        effective_date: datetime.date,
        note: str,
        author_user_id: int,
    ) -> LeaveAdjustmentResultDto:
        """Appends one correction and returns the balance it produced.

        Args:
            session: Active async session.
            user_id: Whose balance is being corrected.
            hours: Signed. Negative books leave taken before the system ran.
            effective_date: The Beijing day it counts for. Not in the future.
            note: Why. Required, since it is the only record of the reason.
            author_user_id: The admin doing it, recorded as ``created_by``.

        Returns:
            The row as written, plus the resulting balance.

        Raises:
            ValueError: The note is blank, the hours are zero, the date is in
                the future, or there is no such person. Each becomes a 400.
        """
        reason = note.strip()
        if not reason:
            raise ValueError("A leave adjustment needs a note saying why.")
        if hours == NO_HOURS:
            raise ValueError("A leave adjustment of zero hours changes nothing.")
        if effective_date > business_today():
            raise ValueError(
                f"{effective_date} is in the future. A balance is the sum of "
                "every row, so hours dated ahead would count from now."
            )
        if await self.users_repository.get_user_by_user_id(session, user_id) is None:
            raise ValueError(f"No user with id {user_id}.")

        await self.leave_ledger_repository.add_entries(
            session,
            [
                LeaveLedgerEntity(
                    user_id=user_id,
                    entry_type=LeaveEntryType.MANUAL_ADJUSTMENT,
                    hours=hours,
                    effective_date=effective_date,
                    note=reason,
                    created_by=author_user_id,
                )
            ],
        )
        await session.commit()

        balance = await self.leave_ledger_repository.balance(session, user_id)
        self.logger.info(
            "Leave balance adjusted by %s: user %s, %s hours on %s",
            author_user_id,
            user_id,
            format_hours(hours),
            effective_date,
        )
        return LeaveAdjustmentResultDto(
            user_id=user_id,
            hours=format_hours(hours),
            effective_date=effective_date,
            note=reason,
            balance_hours=format_hours(balance),
        )
