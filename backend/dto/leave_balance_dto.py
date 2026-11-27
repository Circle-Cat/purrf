from backend.dto.base_dto import BaseDto


class LeaveLedgerEntryDto(BaseDto):
    effectiveDate: str
    # The last day of a request's line; equal to effectiveDate for any other.
    endDate: str
    entryType: str
    hours: str
    note: str | None = None


class LeaveBalanceDto(BaseDto):
    balanceHours: str
    entries: list[LeaveLedgerEntryDto]


class LeaveLedgerRowDto(BaseDto):
    leave_ledger_id: int
    effective_date: str
    # The last day of a request's line; equal to effective_date for any other.
    end_date: str
    user_id: int
    name: str | None = None
    ldap: str | None = None
    entry_type: str
    hours: str
    note: str | None = None


class LeaveLedgerPersonDto(BaseDto):
    user_id: int
    name: str | None = None
    ldap: str | None = None


class LeaveLedgerPageDto(BaseDto):
    entries: list[LeaveLedgerRowDto]
    # Everyone with a ledger row, for the person filter: including people the
    # engine no longer pays, whose history is still on record.
    people: list[LeaveLedgerPersonDto]
    page: int
    page_size: int
    total_entries: int
