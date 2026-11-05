import datetime
from decimal import Decimal

from backend.dto.base_dto import BaseDto


class LeaveAdjustmentRequestDto(BaseDto):
    """One hand-written correction to somebody's ledger.

    The same shape covers both of the things corrections are for: the balance
    carried in from the previous year at launch, and leave already taken this
    year, which arrives as negative hours because a request cannot be dated in
    the past. Only the note tells a later reader which is which, so it is
    required.
    """

    user_id: int
    hours: Decimal
    effective_date: datetime.date
    note: str


class LeaveAdjustmentResultDto(BaseDto):
    """What was written, and the balance it produced.

    Hours are strings fixed to two decimals rather than numbers: FastAPI's
    encoder turns a Decimal into a float, and a balance of 78.46 comes back as
    78.45999999999999.
    """

    user_id: int
    hours: str
    effective_date: datetime.date
    note: str
    balance_hours: str
