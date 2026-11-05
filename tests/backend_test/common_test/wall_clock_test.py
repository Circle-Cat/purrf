import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.common.wall_clock import wall_clock_to_utc


class TestWallClockToUtc(unittest.TestCase):
    def test_converts_a_plain_local_slot(self):
        start, end = wall_clock_to_utc(
            day=date(2026, 6, 1),
            start_time="09:00",
            duration_minutes=60,
            timezone_name="America/New_York",
        )
        # June is EDT, UTC-4.
        self.assertEqual(start, datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc))

    def test_returns_tz_aware_utc(self):
        start, end = wall_clock_to_utc(
            day=date(2026, 6, 1),
            start_time="09:00",
            duration_minutes=30,
            timezone_name="Asia/Shanghai",
        )
        for value in (start, end):
            self.assertIsNotNone(value.tzinfo)
            self.assertEqual(value.utcoffset(), timedelta(0))

    def test_zone_without_dst_is_unaffected_by_the_season(self):
        # Asia/Shanghai has had no DST since 1991, so the same wall-clock time
        # maps to the same offset in January and July. A converter that
        # subtracted a fixed offset would also pass this -- it is here as the
        # control for the two DST cases below, not as the interesting case.
        winter, _ = wall_clock_to_utc(
            day=date(2026, 1, 15),
            start_time="09:00",
            duration_minutes=30,
            timezone_name="Asia/Shanghai",
        )
        summer, _ = wall_clock_to_utc(
            day=date(2026, 7, 15),
            start_time="09:00",
            duration_minutes=30,
            timezone_name="Asia/Shanghai",
        )
        self.assertEqual(winter.hour, 1)
        self.assertEqual(summer.hour, 1)

    def test_the_same_wall_clock_time_maps_to_different_utc_across_a_dst_change(self):
        """The whole reason this helper exists.

        US DST began 2026-03-08. 09:00 local is 14:00Z on the Wednesday before
        (EST, UTC-5) and 13:00Z on the Wednesday after (EDT, UTC-4). A
        converter that subtracted one fixed offset would put both at the same
        UTC hour and silently move every meeting booked across the boundary by
        an hour.
        """
        before, _ = wall_clock_to_utc(
            day=date(2026, 3, 4),
            start_time="09:00",
            duration_minutes=30,
            timezone_name="America/New_York",
        )
        after, _ = wall_clock_to_utc(
            day=date(2026, 3, 11),
            start_time="09:00",
            duration_minutes=30,
            timezone_name="America/New_York",
        )

        self.assertEqual(before, datetime(2026, 3, 4, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(after, datetime(2026, 3, 11, 13, 0, tzinfo=timezone.utc))
        self.assertNotEqual(before.hour, after.hour)

        # And read back in local terms both really are 09:00, which is the
        # contract the callers depend on.
        tz = ZoneInfo("America/New_York")
        self.assertEqual(before.astimezone(tz).hour, 9)
        self.assertEqual(after.astimezone(tz).hour, 9)

    def test_the_same_holds_across_the_autumn_change(self):
        # US DST ended 2026-11-01: 09:00 local is 13:00Z before and 14:00Z after.
        before, _ = wall_clock_to_utc(
            day=date(2026, 10, 28),
            start_time="09:00",
            duration_minutes=30,
            timezone_name="America/New_York",
        )
        after, _ = wall_clock_to_utc(
            day=date(2026, 11, 4),
            start_time="09:00",
            duration_minutes=30,
            timezone_name="America/New_York",
        )
        self.assertEqual(before, datetime(2026, 10, 28, 13, 0, tzinfo=timezone.utc))
        self.assertEqual(after, datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc))

    def test_duration_is_absolute_not_wall_clock(self):
        """A slot that spans the spring-forward hour keeps its real length.

        01:30 local on 2026-03-08 is EST; 60 minutes later the clocks have
        jumped, so the local end time reads 03:30 rather than 02:30. The
        meeting is still one hour long, which is what the attendees agreed to.
        """
        start, end = wall_clock_to_utc(
            day=date(2026, 3, 8),
            start_time="01:30",
            duration_minutes=60,
            timezone_name="America/New_York",
        )
        self.assertEqual(end - start, timedelta(minutes=60))
        local_end = end.astimezone(ZoneInfo("America/New_York"))
        self.assertEqual((local_end.hour, local_end.minute), (3, 30))

    def test_rejects_an_unknown_zone(self):
        with self.assertRaises(Exception):
            wall_clock_to_utc(
                day=date(2026, 6, 1),
                start_time="09:00",
                duration_minutes=30,
                timezone_name="Mars/Phobos",
            )


if __name__ == "__main__":
    unittest.main()
