from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from backend.common.constants import DATE_FORMAT_YMD


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc, hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(
        tzinfo=timezone.utc, hour=23, minute=59, second=59, microsecond=999999
    )


def parse_date_to_utc_datetime(
    date_str: str, start_of_day: bool = True
) -> datetime | None:
    """
    Parses a date string in "YYYY-MM-DD" format into a UTC datetime object.
    Args:
        date_str: Date string in "YYYY-MM-DD" format.
        start_of_day: If True, sets time to 00:00:00.000000;
                         if False, sets time to 23:59:59.999999.
    Return:
        Parsed UTC datetime object or None if date_str is empty.
    Raises ValueError:
        If the date string format is invalid.
    """
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, DATE_FORMAT_YMD)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")

    if start_of_day:
        return _start_of_day(dt)
    else:
        return _end_of_day(dt)


def get_start_end_timestamps(
    start_date_str: str | None, end_date_str: str | None
) -> tuple[datetime, datetime]:
    """
    Calculate UTC start and end datetime objects based on input date strings.

    - Both dates given: parse with day boundaries; cap end date to today if in future; error if end < start.
    - Only start date: end = start + 1 month (capped to today); error if start in future.
    - Only end date: start = end - 1 month; cap end to today if in future.
    - Neither given: last month until today.

    Args:
        start_date_str: Start date string in "YYYY-MM-DD" format or None.
        end_date_str: End date string in "YYYY-MM-DD" format or None.

    Returns:
        Tuple of (start_datetime_utc, end_datetime_utc).

    Raises:
        ValueError: If end date is earlier than start date.
    """
    today_utc = datetime.now(timezone.utc)
    max_end_dt_utc = _end_of_day(today_utc)

    def _cap_to_today(dt: datetime) -> datetime:
        return min(dt, max_end_dt_utc)

    if start_date_str:
        start_dt_utc = parse_date_to_utc_datetime(start_date_str, start_of_day=True)
        if start_dt_utc > max_end_dt_utc:
            raise ValueError(f"Start date {start_date_str} cannot be later than today.")
    if end_date_str:
        end_dt_utc = parse_date_to_utc_datetime(end_date_str, start_of_day=False)
        end_dt_utc = _cap_to_today(end_dt_utc)

    if start_date_str and end_date_str:
        if end_dt_utc < start_dt_utc:
            raise ValueError(
                f"End date {end_date_str} cannot be earlier than start date {start_date_str}."
            )
    elif start_date_str:
        end_dt_utc = _end_of_day(start_dt_utc + relativedelta(months=1))
        end_dt_utc = _cap_to_today(end_dt_utc)
    elif end_date_str:
        start_dt_utc = _start_of_day(end_dt_utc + relativedelta(months=-1))
    else:
        end_dt_utc = max_end_dt_utc
        start_dt_utc = _start_of_day(today_utc + relativedelta(months=-1))

    return start_dt_utc, end_dt_utc
