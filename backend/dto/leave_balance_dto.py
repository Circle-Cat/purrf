from backend.dto.base_dto import BaseDto


class LeaveLedgerEntryDto(BaseDto):
    effectiveDate: str
    entryType: str
    hours: str
    note: str | None = None


class LeaveBalanceDto(BaseDto):
    balanceHours: str
    entries: list[LeaveLedgerEntryDto]


class LeaveLedgerRowDto(BaseDto):
    leave_ledger_id: int
    effective_date: str
    user_id: int
    name: str | None = None
    ldap: str | None = None
    entry_type: str
    hours: str
    note: str | None = None


class LeaveLedgerPageDto(BaseDto):
    entries: list[LeaveLedgerRowDto]
    page: int
    page_size: int
    total_entries: int
