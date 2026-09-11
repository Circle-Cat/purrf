from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.leave_balance_dto import LeaveBalanceDto, LeaveLedgerEntryDto


class LeaveBalanceService:
    """Service for querying employee leave balances and ledger histories."""

    def __init__(self, logger, leave_ledger_repository):
        """
        Args:
            logger: Structured logger.
            leave_ledger_repository (LeaveLedgerRepository): Append-only leave ledger.
        """
        self.logger = logger
        self.leave_ledger_repository = leave_ledger_repository

    async def get_leave_balance(
        self, session: AsyncSession, user_id: int
    ) -> LeaveBalanceDto:
        """Retrieves a user's total balance and complete ledger history.

        Args:
            session: Active async session.
            user_id: Whose leave balance and ledger to read.

        Returns:
            Formatted total balance hours and individual ledger entry DTOs.
        """
        raw_balance = await self.leave_ledger_repository.balance(session, user_id)
        balance_hours_str = f"{raw_balance:.2f}"

        entries_entities = await self.leave_ledger_repository.list_entries(
            session, user_id
        )
        entry_dtos = [
            LeaveLedgerEntryDto(
                effectiveDate=str(entry.effective_date),
                entryType=entry.entry_type,
                hours=f"{entry.hours:.2f}",
                note=entry.note,
            )
            for entry in entries_entities
        ]

        return LeaveBalanceDto(balanceHours=balance_hours_str, entries=entry_dtos)