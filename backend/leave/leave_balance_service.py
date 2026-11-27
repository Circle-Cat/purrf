from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.leave_balance_dto import (
    LeaveBalanceDto,
    LeaveLedgerEntryDto,
    LeaveLedgerPageDto,
    LeaveLedgerPersonDto,
    LeaveLedgerRowDto,
)

from backend.leave.leave_participants import (
    resolve_names_and_ldaps,
)


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

        lines = await self.leave_ledger_repository.list_lines(session, user_id)

        entry_dtos = [
            LeaveLedgerEntryDto(
                effectiveDate=str(line.effective_date),
                endDate=str(line.end_date),
                entryType=line.entry_type,
                hours=f"{line.hours:.2f}",
                note=line.note,
            )
            for line in lines
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
        offset = (page - 1) * page_size

        lines = await self.leave_ledger_repository.list_lines(
            session, user_id, limit=page_size, offset=offset
        )
        total_entries = await self.leave_ledger_repository.count_lines(session, user_id)
        # Note: total_entries is queried separately from the page entries.
        # A concurrent write committed between these two queries (e.g., weekly
        # accruals or manual adjustments) may cause total_entries to slightly
        # disagree with the returned page rows. This is acceptable for an admin view.

        # The filter needs everyone with history, which covers this page too.
        ledger_user_ids = await self.leave_ledger_repository.list_user_ids(session)

        name_by_id, ldap_by_id = await resolve_names_and_ldaps(
            session,
            ledger_user_ids,
            self.users_repository,
            self.user_emails_repository,
        )
        people = sorted(
            (
                LeaveLedgerPersonDto(
                    user_id=user_id,
                    name=name_by_id.get(user_id),
                    ldap=ldap_by_id.get(user_id),
                )
                for user_id in ledger_user_ids
            ),
            key=lambda person: (
                (person.name or "").casefold(),
                person.ldap or "",
                person.user_id,
            ),
        )

        entry_dtos = [
            LeaveLedgerRowDto(
                leave_ledger_id=line.leave_ledger_id,
                effective_date=str(line.effective_date),
                end_date=str(line.end_date),
                user_id=line.user_id,
                name=name_by_id.get(line.user_id),
                ldap=ldap_by_id.get(line.user_id),
                entry_type=line.entry_type.value,
                hours=f"{line.hours:.2f}",
                note=line.note,
            )
            for line in lines
        ]

        return LeaveLedgerPageDto(
            entries=entry_dtos,
            people=people,
            page=page,
            page_size=page_size,
            total_entries=total_entries,
        )
