import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class LeaveHolidayEntity(Base):
    """One company holiday, on the China calendar the leave system runs on.

    These days are not deducted from anyone's balance -- the office is closed,
    so there is nothing to request. ``is_exchangeable`` marks the ones an
    employee may trade for a working day instead.

    The table also answers "has year N been entered yet?", which gates every
    request submission: a year with no rows would otherwise let holidays be
    booked, and silently deducted, as ordinary leave. That question is why
    ``year`` is its own column even though ``date`` already contains it -- the
    check becomes an existence lookup on the leading column of the unique
    constraint instead of a range scan that is easy to get wrong at the year
    boundary. The CHECK stops the two from drifting apart.

    Rows are entered by hand, per environment, and are deliberately not
    migrated. Before chasing an "hours computed wrong" bug that only reproduces
    outside prod, compare the two calendars.
    """

    __tablename__ = "leave_holiday"
    __table_args__ = (
        UniqueConstraint("year", "date"),
        CheckConstraint("year = EXTRACT(YEAR FROM date)", name="year_agrees_with_date"),
    )

    leave_holiday_id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_exchangeable: Mapped[bool] = mapped_column(Boolean, nullable=False)
