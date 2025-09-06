from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from backend.common.constants import (
    DATE_FORMAT_YMD,
    DATETIME_ISO8601_FORMAT,
    DATE_FORMAT_YMD_NOSEP,
)


class DateTimeUtil:
    def __init__(self, logger):
        self.logger = logger

    def format_datetime_to_int(self, dt: datetime) -> int:
        """
        Convert a datetime objectinto an integer in YYYYMMDD format.

        Args:
            dt: A datetime object.

        Returns:
            An integer representation of the date in YYYYMMDD format.
        """
        return int(dt.strftime(DATE_FORMAT_YMD_NOSEP))

    def format_datetime_str_to_int(self, date_str: str) -> int:
        """
        Convert a datetime string (e.g. '2023-07-12T14:35:22.123+0000')
        into an integer in YYYYMMDD format.

        Args:
            date_str: A datetime string in the format "YYYY-MM-DDTHH:MM:SS.mmm±HHMM".

        Returns:
            An integer representation of the date in YYYYMMDD format.
        """
        dt = datetime.strptime(date_str, DATETIME_ISO8601_FORMAT)
        return int(dt.strftime(DATE_FORMAT_YMD_NOSEP))

    def format_datetime_to_iso_utc_z(self, dt_object: datetime) -> str:
        """
        Formats a datetime object into an ISO 8601 string with microseconds
        and 'Z' for UTC timezone.

        Args:
            dt_object (datetime): The datetime object to format.

        Returns:
            str: The formatted ISO 8601 datetime string (e.g., "2023-10-27T10:30:45.123456Z").

        Raises:
            ValueError: If the dt_object is not a valid datetime or if formatting fails.
        """
        if not isinstance(dt_object, datetime):
            raise ValueError("Input must be a datetime object.")
        try:
            return dt_object.isoformat(timespec="microseconds").replace("+00:00", "Z")
        except Exception as e:
            self.logger.error(f"Failed to format datetime object: {e}", exc_info=True)
            raise ValueError(f"Failed to format datetime object: {dt_object}.") from e

    def _start_of_day(self, dt: datetime) -> datetime:
        """Return the UTC datetime at the start of the given day (00:00:00)."""
        return dt.replace(
            tzinfo=timezone.utc, hour=0, minute=0, second=0, microsecond=0
        )

    def _end_of_day(self, dt: datetime) -> datetime:
        """Return the UTC datetime at the end of the given day (23:59:59.999999)."""
        return dt.replace(
            tzinfo=timezone.utc, hour=23, minute=59, second=59, microsecond=999999
        )

    def _cap_to_today(self, dt: datetime, today: datetime) -> datetime:
        """Return the earlier of the given datetime and today's datetime."""
        return min(dt, today)

    def parse_date_to_utc_datetime(
        self, date_str: str, start_of_day: bool = True
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
            return self._start_of_day(dt)
        else:
            return self._end_of_day(dt)

    def get_start_end_timestamps(
        self, start_date_str: str | None, end_date_str: str | None
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
        max_end_dt_utc = self._end_of_day(today_utc)

        if start_date_str:
            start_dt_utc = self.parse_date_to_utc_datetime(
                start_date_str, start_of_day=True
            )
            if start_dt_utc > max_end_dt_utc:
                raise ValueError(
                    f"Start date {start_date_str} cannot be later than today."
                )
        if end_date_str:
            end_dt_utc = self.parse_date_to_utc_datetime(
                end_date_str, start_of_day=False
            )
            end_dt_utc = self._cap_to_today(end_dt_utc, max_end_dt_utc)

        if start_date_str and end_date_str:
            if end_dt_utc < start_dt_utc:
                raise ValueError(
                    f"End date {end_date_str} cannot be earlier than start date {start_date_str}."
                )
        elif start_date_str:
            end_dt_utc = self._end_of_day(start_dt_utc + relativedelta(months=1))
            end_dt_utc = self._cap_to_today(end_dt_utc, max_end_dt_utc)
        elif end_date_str:
            start_dt_utc = self._start_of_day(end_dt_utc + relativedelta(months=-1))
        else:
            end_dt_utc = max_end_dt_utc
            start_dt_utc = self._start_of_day(today_utc + relativedelta(months=-1))

        return start_dt_utc, end_dt_utc


# TODO: Remove Deprecated Standalone Methods After Migration
# See: https://jira.circlecat.org/browse/PUR-140
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
