"""Company holidays as rows, and as the segments the calendar page shows.

Storage is one row per day. Entry and display are per segment -- a run of
consecutive days under one name, like ``2/17 - 2/21 Spring Festival week 2``.
A segment has no identity of its own: it is a reading of the rows, which is
why a year is replaced whole rather than segment by segment.

Both directions here refuse to paper over a mistyped date. Grouping splits on
any discontinuity, so a wrong date shows up as a segment that broke in two
instead of one that quietly spans the gap; expanding validates before it
produces anything, so an admin gets a sentence rather than a Postgres
constraint error or a day that silently disappears.
"""

import datetime

from backend.dto.leave_holiday_dto import (
    LeaveHolidaySegmentDto,
    LeaveHolidaySegmentInputDto,
)
from backend.entity.leave_holiday_entity import LeaveHolidayEntity

ONE_DAY = datetime.timedelta(days=1)


def group_into_segments(
    holidays: list[LeaveHolidayEntity],
) -> list[LeaveHolidaySegmentDto]:
    """Groups holiday rows into the segments the page renders.

    Args:
        holidays: One year's rows, ascending by date. The order is the
            repository's job; grouping trusts it.

    Returns:
        Segments in the same order, one per run of days that share a name, sit
        on consecutive dates and agree on ``is_exchangeable``.
    """
    segments: list[LeaveHolidaySegmentDto] = []
    previous: LeaveHolidayEntity | None = None

    for holiday in holidays:
        if previous is not None and _continues(previous, holiday):
            open_segment = segments[-1]
            segments[-1] = open_segment.model_copy(
                update={
                    "end_date": holiday.date,
                    "day_count": open_segment.day_count + 1,
                }
            )
        else:
            segments.append(
                LeaveHolidaySegmentDto(
                    name=holiday.name,
                    start_date=holiday.date,
                    end_date=holiday.date,
                    day_count=1,
                    is_exchangeable=holiday.is_exchangeable,
                )
            )
        previous = holiday

    return segments


def expand_segments(
    year: int, segments: list[LeaveHolidaySegmentInputDto]
) -> list[LeaveHolidayEntity]:
    """Validates a year's segments and expands them to one row per day.

    Validation lives here rather than beside it so that no caller can write
    rows without it. Every rejection is a ``ValueError``, which the global
    handler turns into a 400 carrying the message.

    Args:
        year: The year being replaced.
        segments: Its complete segment list.

    Returns:
        Rows ascending by date, ready to be written.

    Raises:
        ValueError: The list is empty; a name is blank; a segment ends before
            it starts; a date falls outside ``year``; or two segments claim
            the same day.
    """
    if not segments:
        raise ValueError(
            f"A year needs at least one company holiday. Leaving {year} empty "
            "would refuse every leave request dated in it."
        )

    claimed_by: dict[datetime.date, str] = {}
    rows: list[LeaveHolidayEntity] = []

    for segment in segments:
        name = segment.name.strip()
        if not name:
            raise ValueError("Every company holiday needs a name.")
        if segment.end_date < segment.start_date:
            raise ValueError(f"{name} ends before it starts.")
        if segment.start_date.year != segment.end_date.year:
            raise ValueError(
                f"{name} spans two years. Enter it as two segments, one per year."
            )
        if segment.start_date.year != year:
            raise ValueError(f"{name} falls in {segment.start_date.year}, not {year}.")

        day = segment.start_date
        while day <= segment.end_date:
            if day in claimed_by:
                raise ValueError(f"{name} and {claimed_by[day]} both cover {day}.")
            claimed_by[day] = name
            rows.append(
                LeaveHolidayEntity(
                    year=year,
                    date=day,
                    name=name,
                    is_exchangeable=segment.is_exchangeable,
                )
            )
            day += ONE_DAY

    rows.sort(key=lambda row: row.date)
    return rows


def _continues(previous: LeaveHolidayEntity, holiday: LeaveHolidayEntity) -> bool:
    """Whether ``holiday`` extends the segment ``previous`` ends.

    ``is_exchangeable`` is part of the test on purpose. Entry sets one flag per
    segment, so two values inside one run can only come from hand-written SQL;
    showing that as a split makes it visible instead of silently taking the
    first row's value.
    """
    return (
        holiday.name == previous.name
        and holiday.date == previous.date + ONE_DAY
        and holiday.is_exchangeable == previous.is_exchangeable
    )
