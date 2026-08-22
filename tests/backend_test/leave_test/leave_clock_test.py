"""The one source of "today" for anything leave-related."""

import datetime
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend.leave.leave_clock import business_today


class TestBusinessToday(unittest.TestCase):
    @patch("backend.leave.leave_clock.datetime")
    def test_the_beijing_day_wins_over_the_utc_day(self, mock_datetime):
        """Business dates are Beijing civil days while the pods run on UTC, so
        between 00:00 and 08:00 Beijing the two disagree. Every cron schedule
        in helm is written in UTC, which makes that window easy to land in."""
        mock_datetime.now.side_effect = lambda tz: datetime.datetime(
            2026, 1, 1, 2, 30, tzinfo=ZoneInfo("Asia/Shanghai")
        )

        self.assertEqual(business_today(), datetime.date(2026, 1, 1))
        mock_datetime.now.assert_called_once()

    def test_it_asks_for_the_shanghai_zone_rather_than_the_local_one(self):
        """date.today() and utcnow() are both wrong here and neither raises."""
        with patch("backend.leave.leave_clock.datetime") as mock_datetime:
            business_today()

        requested_zone = mock_datetime.now.call_args.args[0]
        self.assertEqual(str(requested_zone), "Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
