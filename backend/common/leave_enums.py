from enum import StrEnum


class LeaveEntryType(StrEnum):
    """What produced a ledger row.

    Every type is a reason attached to a number, with two asymmetries. The
    accrual engine counts only ``WEEKLY_ACCRUAL`` as "already granted" when it
    works out what this week still owes, so counting a second type there would
    quietly change everyone's entitlement rather than fail. And
    ``LEVEL_CHANGE`` is the one type that carries no hours: it is read for its
    date, not its amount.
    """

    WEEKLY_ACCRUAL = "weekly_accrual"
    LEAVE_DEDUCTION = "leave_deduction"
    EXCHANGE_CREDIT = "exchange_credit"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    CARRYOVER_FORFEIT = "carryover_forfeit"
    # Always zero hours. It marks the day an annual entitlement changed, which
    # is where the accrual engine restarts its proportion from; carrying no
    # hours is what lets a balance stay the plain sum of every row, with no
    # type filter that a reader could forget.
    LEVEL_CHANGE = "level_change"


# The types a job pays hours out with. The partial unique index on
# leave_ledger covers exactly these; the entity explains why LEVEL_CHANGE,
# which a job also writes, stays outside it.
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

    ``PENDING`` may be withdrawn by the employee alone -- nothing has reached
    the ledger yet. Approval is the end of the line: an approved request cannot
    be taken back, by either side. Somebody who does not end up taking approved
    leave has spent the hours, and putting them back is an admin adjustment
    with a note on it.

    There is deliberately no state for cancelling an approved request. Leaving
    one in the enum would read as a feature that exists.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
