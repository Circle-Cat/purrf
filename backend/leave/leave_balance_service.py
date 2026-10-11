from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.leave_balance_dto import (
    LeaveBalanceDto,
    LeaveLedgerEntryDto,
    LeaveLedgerPageDto,
    LeaveLedgerRowDto,
)

from backend.leave.leave_participants import ldap_from_addresses
from backend.common.name_utils import user_display_name


class LeaveBalanceService:
    """Service for querying employee leave balances and ledger histories."""

    def __init__(
        self,
        logger,
        leave_ledger_repository,
        users_repository,
        user_emails_repository,
    ):
        """
        Args:
            logger: Structured logger.
            leave_ledger_repository (LeaveLedgerRepository): Append-only leave ledger.
            users_repository (UsersRepository): Internal employee profiles and names.
            user_emails_repository (UserEmailsRepository): Email addresses to resolve Azure ldaps.
        """
        self.logger = logger
        self.leave_ledger_repository = leave_ledger_repository
        self.users_repository = users_repository
        self.user_emails_repository = user_emails_repository

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
        if user_id is None or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

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

    async def list_ledger(
        self,
        session: AsyncSession,
        *,
        user_id: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> LeaveLedgerPageDto:
        """Retrieves a paginated list of ledger entries across all users or a specific user.

        Args:
            session: Active async session.
            user_id: Optional user filter. None retrieves entries for all users.
            page: 1-based page index.
            page_size: Number of entries per page.

        Returns:
            Paginated DTO containing detailed ledger rows with resolved user names and ldaps.
        """
        # Calculate database pagination offset
        offset = (page - 1) * page_size

        # Query entries for the current page and total entries matching the filter
        entries_entities = await self.leave_ledger_repository.list_entries(
            session, user_id, limit=page_size, offset=offset
        )
        total_entries = await self.leave_ledger_repository.count_entries(
            session, user_id
        )

        # Extract user_ids for the current page only to avoid bulk loading unnecessary accounts
        page_user_ids = sorted({entry.user_id for entry in entries_entities})

        # Batch fetch user records and build display name mapping
        users = await self.users_repository.get_all_by_ids(session, page_user_ids)
        name_by_id = {
            user.user_id: user_display_name(
                first_name=user.first_name,
                last_name=user.last_name,
                preferred_name=user.preferred_name,
            )
            for user in users
        }

        # Batch fetch user emails and resolve ldaps using ldap_from_addresses
        addresses_by_id = await self.user_emails_repository.get_emails_by_user_ids(
            session, page_user_ids
        )
        ldap_by_id = {
            uid: ldap_from_addresses(addresses)
            for uid, addresses in addresses_by_id.items()
        }

        # Map current page entities into LeaveLedgerRowDto instances
        entry_dtos = [
            LeaveLedgerRowDto(
                leave_ledger_id=entry.leave_ledger_id,
                effective_date=str(entry.effective_date),
                user_id=entry.user_id,
                name=name_by_id.get(entry.user_id),
                ldap=ldap_by_id.get(entry.user_id),
                entry_type=entry.entry_type.value
                if hasattr(entry.entry_type, "value")
                else str(entry.entry_type),
                hours=f"{entry.hours:.2f}",
                note=entry.note,
            )
            for entry in entries_entities
        ]

        # Assemble and return the paginated DTO
        return LeaveLedgerPageDto(
            entries=entry_dtos,
            page=page,
            page_size=page_size,
            total_entries=total_entries,
        )
