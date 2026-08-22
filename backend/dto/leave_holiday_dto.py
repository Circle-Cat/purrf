import datetime

from backend.dto.base_dto import BaseDto


class LeaveHolidaySegmentDto(BaseDto):
    """A run of consecutive company-holiday days sharing one name.

    There is no id, because a segment is not an entity -- it is a way of
    reading the rows. Nothing can address one, which is why the calendar is
    replaced a year at a time rather than segment by segment.
    """

    name: str
    start_date: datetime.date
    end_date: datetime.date
    day_count: int
    is_exchangeable: bool


class LeaveCalendarYearDto(BaseDto):
    """One year of company holidays, as the calendar page reads it."""

    year: int
    segments: list[LeaveHolidaySegmentDto]
    total_days: int


class LeaveHolidaySegmentInputDto(BaseDto):
    """A segment as it is entered.

    ``is_exchangeable`` is one flag for the whole segment: a holiday is either
    tradeable or it is not. Choosing part of one is the employee's side of it,
    at request time, not something the calendar records.
    """

    name: str
    start_date: datetime.date
    end_date: datetime.date
    is_exchangeable: bool = False


class LeaveCalendarReplaceRequestDto(BaseDto):
    """The whole of one year. Anything absent from it is deleted."""

    segments: list[LeaveHolidaySegmentInputDto]


class LeaveHolidayYearsDto(BaseDto):
    """Which years hold rows, and which two the page must offer regardless.

    ``current_year`` and ``next_year`` come from the server so that a browser
    in another timezone cannot disagree about which year it is.
    """

    years: list[int]
    current_year: int
    next_year: int


class LeavePolicyDto(BaseDto):
    """The leave constants, read-only. Changing any of them is a pull request.

    ``weekend_labels`` is rendered rather than derived in the browser:
    ``datetime.weekday()`` counts Monday as 0 while JavaScript's ``getDay()``
    counts Sunday as 0, and translating between them client-side is a mistake
    waiting to happen.

    A ``None`` ceiling means the ceiling is not in force, which is not the same
    as ``0`` -- that would forbid carrying over a single hour.
    """

    weekend_weekdays: list[int]
    weekend_labels: list[str]
    hours_per_day: int
    annual_hours_by_level: dict[str, int]
    max_carryover_hours: int | None
    max_overdraft_hours: int | None
