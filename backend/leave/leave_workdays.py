"""Working days, and the two numbers derived from them.

One definition of a working day serves both the hours a request deducts and the
notice it gave. A second definition would agree on most inputs and disagree on
the ones nobody tries.

A working day is any day that is neither a weekend day -- Sunday and Monday
here -- nor a company holiday. Company holidays are passed in rather than
looked up: they are entered by hand per environment, and a function that
fetched them would be one that could quietly compute against an empty calendar.
"""

import datetime
import math
from decimal import Decimal

from backend.common.leave_enums import LeaveRequestType
from backend.leave.leave_policy import HOURS_PER_DAY, WEEKEND_WEEKDAYS

ONE_DAY = datetime.timedelta(days=1)

HALF_HOUR_MINUTES = 30

NO_HOURS = Decimal("0.00")


def is_workday(day: datetime.date, holidays: frozenset[datetime.date]) -> bool:
    """Whether work happens on ``day``.

    Args:
        day: The Beijing calendar day.
        holidays: The company holidays of every year the caller cares about.

    Returns:
        True unless it is a weekend day or a company holiday.
    """
    return day.weekday() not in WEEKEND_WEEKDAYS and day not in holidays


def count_workdays(
    first: datetime.date, last: datetime.date, holidays: frozenset[datetime.date]
) -> int:
    """Working days in ``[first, last]``, both ends included.

    Args:
        first: First day of the range.
        last: Last day, counted.
        holidays: Company holidays.

    Returns:
        How many of those days are working days. Zero for a range made
        entirely of days off, and for a range that runs backwards.
    """
    day = first
    total = 0
    while day <= last:
        if is_workday(day, holidays):
            total += 1
        day += ONE_DAY
    return total


def workdays_before(
    submitted_on: datetime.date,
    first_leave_day: datetime.date,
    holidays: frozenset[datetime.date],
) -> int:
    """Working days of notice a request gave.

    The day of submission counts and the first day off does not. That side is
    chosen rather than incidental: reversing it turns the design's own
    compliant example into a late one.

    Args:
        submitted_on: The Beijing day the request was submitted.
        first_leave_day: The first day of the leave.
        holidays: Company holidays.

    Returns:
        The count over ``[submitted_on, first_leave_day)``. Zero when leave
        starts the day it is asked for, which is late notice rather than an
        error.
    """
    if first_leave_day <= submitted_on:
        return 0
    return count_workdays(submitted_on, first_leave_day - ONE_DAY, holidays)


def required_notice_workdays(hours: Decimal) -> int:
    """Working days of notice a request of ``hours`` should have given.

    Whole days first, rounded up: four hours off and eight ask for the same
    notice, because the day still has to be covered.

    Args:
        hours: The request's hours.

    Returns:
        Twice the number of days, rounded up.
    """
    days = math.ceil(hours / HOURS_PER_DAY)
    return 2 * days


def request_hours(
    request_type: LeaveRequestType,
    start_date: datetime.date,
    end_date: datetime.date,
    start_time: datetime.time | None,
    end_time: datetime.time | None,
    holidays: frozenset[datetime.date],
) -> Decimal:
    """What one request is worth in hours.

    Leave and exchange count opposite things. Leave skips the days nobody
    works: a range covering a company holiday and a weekend deducts only what
    is left. An exchange counts every day in its range, because a range holding
    a day that cannot be exchanged is refused outright -- there is no day to
    skip, and skipping one would mean somebody worked and was not credited.

    Args:
        request_type: Paid, sick or exchange.
        start_date: First day.
        end_date: Last day. Equal to ``start_date`` for one day.
        start_time: Only meaningful for a single day of leave.
        end_time: As above.
        holidays: Company holidays.

    Returns:
        Hours, to two decimal places. Zero when a single day of leave falls on
        a day off -- there is nothing to deduct, and the caller refuses a
        request worth nothing rather than storing one.

    Raises:
        ValueError: Times were sent where they have no reading -- on an
            exchange, on a range of days, or with only one end given; or a
            single day's times run backwards, exceed a working day, or fall
            off the half hour. Nothing here is rounded or dropped: acting on a
            request nobody meant to make is worse than refusing it.
    """
    return sum(
        (
            hours
            for _, hours in hours_by_day(
                request_type, start_date, end_date, start_time, end_time, holidays
            )
        ),
        NO_HOURS,
    )


def hours_by_day(
    request_type: LeaveRequestType,
    start_date: datetime.date,
    end_date: datetime.date,
    start_time: datetime.time | None,
    end_time: datetime.time | None,
    holidays: frozenset[datetime.date],
) -> list[tuple[datetime.date, Decimal]]:
    """The days one request covers and the hours each is worth.

    The rules :func:`request_hours` describes, applied a day at a time; that
    total is the sum of this list, so the two cannot disagree. A day worth
    nothing -- a weekend day or a holiday inside a range of leave -- is left
    out rather than listed at zero.

    Args:
        request_type: Paid, sick or exchange.
        start_date: First day.
        end_date: Last day. Equal to ``start_date`` for one day.
        start_time: Only meaningful for a single day of leave.
        end_time: As above.
        holidays: Company holidays.

    Returns:
        ``(day, hours)`` in date order. Empty when a single day of leave falls
        on a day off.

    Raises:
        ValueError: As :func:`request_hours`.
    """
    days = [
        start_date + ONE_DAY * offset
        for offset in range((end_date - start_date).days + 1)
    ]
    has_times = start_time is not None or end_time is not None
    whole_day = Decimal(HOURS_PER_DAY).quantize(NO_HOURS)

    if request_type is LeaveRequestType.EXCHANGE:
        if has_times:
            raise ValueError(
                "An exchange covers whole days: half a day back at work is not "
                "on offer."
            )
        return [(day, whole_day) for day in days]

    if has_times:
        if len(days) > 1:
            raise ValueError(
                "A range of days is taken whole. Times describe one day, so a "
                "part day has to be asked for on its own."
            )
        if start_time is None or end_time is None:
            raise ValueError(
                "A part day needs both ends. One time on its own says when it "
                "starts or when it stops, never how long it lasts."
            )

    if not has_times:
        return [(day, whole_day) for day in days if is_workday(day, holidays)]

    if not is_workday(start_date, holidays):
        return []

    return [(start_date, _hours_between(start_time, end_time))]


def days_not_counted(
    request_type: LeaveRequestType,
    start_date: datetime.date,
    end_date: datetime.date,
    start_time: datetime.time | None,
    end_time: datetime.time | None,
    holidays: frozenset[datetime.date],
) -> list[datetime.date]:
    """The days inside a request's range that it takes no hours for.

    The complement of :func:`hours_by_day` over the same range, so the days
    shown as skipped and the hours charged come from one rule. An exchange
    skips nothing: a range holding a day off is refused before it is filed.

    Args:
        request_type: Paid, sick or exchange.
        start_date: First day.
        end_date: Last day.
        start_time: As :func:`hours_by_day`.
        end_time: As :func:`hours_by_day`.
        holidays: Company holidays.

    Returns:
        The skipped days in date order; empty when every day counts.

    Raises:
        ValueError: As :func:`request_hours`.
    """
    counted = {
        day
        for day, _ in hours_by_day(
            request_type, start_date, end_date, start_time, end_time, holidays
        )
    }
    return [
        start_date + ONE_DAY * offset
        for offset in range((end_date - start_date).days + 1)
        if start_date + ONE_DAY * offset not in counted
    ]


def _hours_between(start_time: datetime.time, end_time: datetime.time) -> Decimal:
    """The span between two times on one day, in hours.

    Raises:
        ValueError: The span runs backwards, is longer than a working day, or
            either end falls off the half hour.
    """
    for edge in (start_time, end_time):
        if edge.minute % HALF_HOUR_MINUTES or edge.second or edge.microsecond:
            raise ValueError(
                f"{edge:%H:%M} is not on the half hour. Leave is taken in "
                "half-hour steps."
            )

    minutes = (end_time.hour * 60 + end_time.minute) - (
        start_time.hour * 60 + start_time.minute
    )
    if minutes <= 0:
        raise ValueError(f"{end_time:%H:%M} is not after {start_time:%H:%M}.")

    hours = Decimal(minutes) / Decimal(60)
    if hours > HOURS_PER_DAY:
        raise ValueError(
            f"{hours:.2f} hours is longer than a working day of {HOURS_PER_DAY}."
        )
    return hours.quantize(NO_HOURS)
