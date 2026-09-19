from backend.dto.base_dto import BaseDto


class LeaveLedgerEntryDto(BaseDto):
    effectiveDate: str
    entryType: str
    hours: str
    note: str | None = None


class LeaveBalanceDto(BaseDto):
    balanceHours: str
    entries: list[LeaveLedgerEntryDto]
