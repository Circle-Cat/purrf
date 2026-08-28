"""The one source of "today" for anything leave-related."""

import datetime
import unittest
from unittest.mock import patch

from backend.leave.leave_clock import business_today


def _clock_fixed_at(instant):
    """Stands in for a wall clock stopped at one UTC instant.

    Reading it without naming a zone yields the UTC wall time, which is what
    lets the Beijing-day case fail when the zone is dropped.
    """
    return lambda tz=None: (
        instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    )


class TestBusinessToday(unittest.TestCase):
    @patch("backend.leave.leave_clock.datetime")
    def test_the_beijing_day_wins_over_the_utc_day(self, mock_datetime):
        """17:00 UTC is already tomorrow in Beijing. A job scheduled in that
        window would accrue under yesterday's date and collide with the row it
        already wrote. Every cron schedule in helm is written in UTC, which
        makes that window easy to land in."""
        mock_datetime.now.side_effect = _clock_fixed_at(
            datetime.datetime(2026, 8, 12, 17, 0, tzinfo=datetime.timezone.utc)
        )

        self.assertEqual(business_today(), datetime.date(2026, 8, 13))

    def test_it_asks_for_the_shanghai_zone_rather_than_the_local_one(self):
        """date.today() and utcnow() are both wrong here and neither raises."""
        with patch("backend.leave.leave_clock.datetime") as mock_datetime:
            business_today()

        requested_zone = mock_datetime.now.call_args.args[0]
        self.assertEqual(str(requested_zone), "Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
