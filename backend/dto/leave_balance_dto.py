from typing import List, Optional
from pydantic import BaseModel

class LeaveLedgerEntryDto(BaseModel):
    effectiveDate: str
    entryType: str
    hours: str
    note: Optional[str] = None

class LeaveBalanceDto(BaseModel):
    balanceHours: str
    entries: List[LeaveLedgerEntryDto]