from enum import StrEnum


class LeaveEntryType(StrEnum):
    """What produced a ledger row.

    Every type is a reason attached to a number, with one asymmetry:
    ``WEEKLY_ACCRUAL`` is the only type the accrual engine counts as "already
    granted" when it works out what this week still owes. Counting a second
    type there would quietly change everyone's entitlement rather than fail.
    """

    WEEKLY_ACCRUAL = "weekly_accrual"
    LEAVE_DEDUCTION = "leave_deduction"
    EXCHANGE_CREDIT = "exchange_credit"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    REVERSAL = "reversal"
    CARRYOVER_FORFEIT = "carryover_forfeit"


# Types written by a scheduled job rather than by a person. The partial unique
# index on leave_ledger covers exactly these; the entity explains why.
JOB_WRITTEN_ENTRY_TYPES = (
    LeaveEntryType.WEEKLY_ACCRUAL,
    LeaveEntryType.CARRYOVER_FORFEIT,
)


class LeaveRequestType(StrEnum):
    """What is being requested.

    Unpaid leave is out of scope for now; adding it is an enum migration plus
    a branch in the approval path.
    """

    PAID = "paid"
    SICK = "sick"
    EXCHANGE = "exchange"


class LeaveRequestStatus(StrEnum):
    """Where a request sits in its lifecycle.

    ``PENDING`` requests may be withdrawn by the employee alone -- nothing has
    reached the ledger yet. Once approved, undoing it needs the manager again,
    which is what ``CANCEL_PENDING`` is for: approving that transition writes a
    reversal, rejecting it returns the request to ``APPROVED`` untouched.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
