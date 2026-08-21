import datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.leave_enums import JOB_WRITTEN_ENTRY_TYPES, LeaveEntryType

_JOB_WRITTEN_VALUES = ", ".join(f"'{entry.value}'" for entry in JOB_WRITTEN_ENTRY_TYPES)


class LeaveLedgerEntity(Base):
    """Append-only record of every hour granted to or spent by one person.

    A balance is the signed sum of these rows. There is no balance column
    anywhere and no second source of truth, so nothing can disagree with the
    history.

    Nothing here is ever edited or deleted. Cancelling an approved request
    writes a REVERSAL row against the original rather than removing it, which
    is what keeps "why is this number what it is" answerable months later.

    ``created_by`` is NULL when a scheduled job wrote the row rather than a
    person. Readers have to keep that meaning distinct from "a person did it
    but their row is gone".
    """

    __tablename__ = "leave_ledger"
    __table_args__ = (
        # Deliberately partial. It covers the two types a cron pays hours out
        # with, and a cron can run twice -- a retried pod, a manual re-trigger
        # -- so either would double-grant or double-forfeit. Every other type
        # is outside it on purpose, because for those a second row on the same
        # day is a second real event: an admin may book several corrections for
        # one person in a day, and a level may be raised and put back inside
        # one day. Rejecting those would drop the event rather than dedupe it.
        Index(
            "uq_leave_ledger_job_written_entry",
            "user_id",
            "entry_type",
            "effective_date",
            unique=True,
            postgresql_where=text(f"entry_type IN ({_JOB_WRITTEN_VALUES})"),
        ),
    )

    leave_ledger_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    entry_type: Mapped[LeaveEntryType] = mapped_column(
        Enum(
            LeaveEntryType,
            name="leave_entry_type_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    # Signed: grants are positive, deductions negative. A reversal takes the
    # opposite sign of whatever it undoes, and a level change carries zero --
    # it is a marker, not money, so a balance needs no type filter.
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    # The Beijing calendar day the entry counts for, which is not necessarily
    # the day it was written: the annual trim runs on 1 January and dates its
    # rows to 31 December.
    effective_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    source_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("leave_request.leave_request_id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    created_timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
