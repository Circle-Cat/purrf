"""Turning a local wall-clock slot into a UTC interval.

Both scheduling domains take the same shape of input from the browser -- a
local date, an ``HH:MM`` local time, a duration, and the IANA zone those are
meant in -- because the server, not the browser, owns the conversion. This is
the one place that conversion happens.

It used to happen in two: ``interview_scheduling_service._to_utc`` and the
loop body of ``meeting_service._expand_occurrences``. Those few lines encode a
correctness decision rather than plain arithmetic, and having two copies of it
meant a future "simplification" of one could silently diverge from the other,
with no test able to notice.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_UTC = timezone.utc


def wall_clock_to_utc(
    day: date,
    start_time: str,
    duration_minutes: int,
    timezone_name: str,
) -> tuple[datetime, datetime]:
    """Convert a local wall-clock slot to a tz-aware UTC start and end.

    The zone is attached to a naive local datetime rather than subtracting an
    offset, so the offset comes from that zone's rules **on that date**. A
    fixed offset would be right for most of the year and silently shift every
    slot booked across a daylight-saving change by an hour.

    The duration is added after the conversion, so it is an absolute length. A
    slot that spans a spring-forward hour stays as long as the attendees
    agreed; its local end time is what moves.

    Args:
        day (date): The local calendar date of the slot.
        start_time (str): Local start time as ``"HH:MM"``.
        duration_minutes (int): Length of the slot in minutes.
        timezone_name (str): IANA zone the date and time are meant in.

    Returns:
        tuple[datetime, datetime]: ``(start_utc, end_utc)``, both tz-aware UTC.

    Raises:
        ValueError: ``start_time`` is not ``HH:MM``.
        ZoneInfoNotFoundError: ``timezone_name`` is not a known IANA zone.
    """
    hour, minute = (int(part) for part in start_time.split(":"))
    naive = datetime(day.year, day.month, day.day, hour, minute)
    start_utc = naive.replace(tzinfo=ZoneInfo(timezone_name)).astimezone(_UTC)
    return start_utc, start_utc + timedelta(minutes=duration_minutes)
