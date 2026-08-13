import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Time,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.leave_enums import LeaveRequestStatus, LeaveRequestType


class LeaveRequestEntity(Base):
    """One request for leave, or to exchange a company holiday.

    Exchange is not a fourth table: it is this row with a positive entry in the
    ledger instead of a negative one.

    ``hours`` is computed by the system from the dates, the times and the
    calendar -- never supplied by the requester -- because it has to agree with
    what the ledger deducts.

    ``approver_user_id`` is snapshotted from the Azure manager relationship at
    submission and never resolved live: once someone changes manager, the
    historical record must still name whoever actually approved. It is NOT
    NULL, so a person with no manager in Azure cannot submit anything at all,
    sick leave included. That is the intended side: auto-approving instead
    would make "HR left the field blank" indistinguishable from "this person
    genuinely has no supervisor", and let unreviewed requests take effect.
    """

    __tablename__ = "leave_request"
    __table_args__ = (
        # Times describe one calendar day, so a multi-day range cannot carry
        # them: a request from the 3rd at 14:00 to the 5th at 16:00 has no
        # single reading. Part days are single-day by construction.
        CheckConstraint(
            "start_date = end_date OR (start_time IS NULL AND end_time IS NULL)",
            name="times_only_on_a_single_day",
        ),
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
    )

    leave_request_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[LeaveRequestType] = mapped_column(
        Enum(
            LeaveRequestType,
            name="leave_request_type_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    # NULL on both means a whole day. Wall-clock only: they are subtracted from
    # each other and never carry a zone.
    start_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[LeaveRequestStatus] = mapped_column(
        Enum(
            LeaveRequestStatus,
            name="leave_request_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    approver_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"), index=True, nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    is_overdraft: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Set when a paid request gives less notice than the rule requires. Sick
    # leave is exempt and stays false; an exchange that falls short is refused
    # at submission rather than flagged, so it stays false too.
    is_late_notice: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # NULL while pending. Also NULL once decided, when nobody decided it: a
    # short sick request is approved by rule, not by a person.
    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
