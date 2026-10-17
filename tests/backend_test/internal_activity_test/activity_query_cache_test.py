from datetime import datetime, timedelta, timezone
from unittest import TestCase, main
from unittest.mock import MagicMock

from backend.internal_activity_service.activity_query_cache import (
    ActivityQueryCache,
)

NOW = datetime(2026, 10, 17, 15, 0, tzinfo=timezone.utc)
YESTERDAY_END = datetime(2026, 10, 16, 23, 59, 59, 999999, tzinfo=timezone.utc)
TODAY_END = datetime(2026, 10, 17, 23, 59, 59, 999999, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


class TestActivityQueryCache(TestCase):
    def setUp(self):
        self.clock = FakeClock(NOW)
        self.cache = ActivityQueryCache(
            logger=MagicMock(), clock=self.clock, max_entries=3
        )
        self.compute = MagicMock(side_effect=lambda: {"alice": [1, 2]})

    def test_second_lookup_is_served_without_computing_again(self):
        first = self.cache.get_or_compute("m", ("a",), YESTERDAY_END, self.compute)
        second = self.cache.get_or_compute("m", ("a",), YESTERDAY_END, self.compute)

        self.assertEqual(first, {"alice": [1, 2]})
        self.assertEqual(second, {"alice": [1, 2]})
        self.compute.assert_called_once()

    def test_range_ending_before_today_lives_24_hours(self):
        self.cache.get_or_compute("m", ("a",), YESTERDAY_END, self.compute)

        self.clock.advance(hours=23, minutes=59)
        self.cache.get_or_compute("m", ("a",), YESTERDAY_END, self.compute)
        self.assertEqual(self.compute.call_count, 1)

        self.clock.advance(minutes=1)
        self.cache.get_or_compute("m", ("a",), YESTERDAY_END, self.compute)
        self.assertEqual(self.compute.call_count, 2)

    def test_range_including_today_lives_1_hour(self):
        self.cache.get_or_compute("m", ("a",), TODAY_END, self.compute)

        self.clock.advance(minutes=59)
        self.cache.get_or_compute("m", ("a",), TODAY_END, self.compute)
        self.assertEqual(self.compute.call_count, 1)

        self.clock.advance(minutes=1)
        self.cache.get_or_compute("m", ("a",), TODAY_END, self.compute)
        self.assertEqual(self.compute.call_count, 2)

    def test_no_range_end_lives_1_hour(self):
        self.cache.get_or_compute("m", ("a",), None, self.compute)

        self.clock.advance(hours=1)
        self.cache.get_or_compute("m", ("a",), None, self.compute)

        self.assertEqual(self.compute.call_count, 2)

    def test_today_is_the_utc_date(self):
        # 23:30 in Los Angeles on the 16th is already the 17th in UTC, so a
        # range ending on the 16th (UTC) is in the past.
        self.clock.now = datetime(2026, 10, 17, 6, 30, tzinfo=timezone.utc)
        self.cache.get_or_compute("m", ("a",), YESTERDAY_END, self.compute)

        self.clock.advance(hours=2)
        self.cache.get_or_compute("m", ("a",), YESTERDAY_END, self.compute)

        self.compute.assert_called_once()

    def test_different_args_do_not_share_an_entry(self):
        a = self.cache.get_or_compute("m", ("a",), None, lambda: "A")
        b = self.cache.get_or_compute("m", ("b",), None, lambda: "B")
        other_method = self.cache.get_or_compute("n", ("a",), None, lambda: "N")

        self.assertEqual((a, b, other_method), ("A", "B", "N"))

    def test_unordered_ignores_order_but_keeps_duplicates(self):
        self.assertEqual(
            ActivityQueryCache.unordered(["b", "a"]),
            ActivityQueryCache.unordered(["a", "b"]),
        )
        self.assertNotEqual(
            ActivityQueryCache.unordered(["a", "a"]),
            ActivityQueryCache.unordered(["a"]),
        )
        self.assertIsNone(ActivityQueryCache.unordered(None))
        self.assertIsNone(ActivityQueryCache.unordered([]))

    def test_ordered_keeps_order(self):
        self.assertNotEqual(
            ActivityQueryCache.ordered(["b", "a"]),
            ActivityQueryCache.ordered(["a", "b"]),
        )
        self.assertIsNone(ActivityQueryCache.ordered([]))

    def test_least_recently_used_entry_is_evicted_at_the_bound(self):
        for key in ("a", "b", "c"):
            self.cache.get_or_compute("m", (key,), None, lambda: key)
        # Touch "a" so "b" becomes the oldest.
        self.cache.get_or_compute("m", ("a",), None, self.compute)
        self.cache.get_or_compute("m", ("d",), None, lambda: "d")

        self.compute.assert_not_called()
        self.assertEqual(len(self.cache), 3)
        recomputed = self.cache.get_or_compute("m", ("b",), None, lambda: "b2")
        self.assertEqual(recomputed, "b2")

    def test_failure_is_not_cached(self):
        failing = MagicMock(side_effect=RuntimeError("redis down"))

        with self.assertRaises(RuntimeError):
            self.cache.get_or_compute("m", ("a",), None, failing)
        result = self.cache.get_or_compute("m", ("a",), None, lambda: "ok")

        self.assertEqual(result, "ok")
        self.assertEqual(len(self.cache), 1)

    def test_caller_mutating_a_result_does_not_change_the_cached_value(self):
        first = self.cache.get_or_compute("m", ("a",), None, self.compute)
        first["alice"].append(3)
        first["bob"] = []

        second = self.cache.get_or_compute("m", ("a",), None, self.compute)
        second["alice"].append(4)
        third = self.cache.get_or_compute("m", ("a",), None, self.compute)

        self.assertEqual(third, {"alice": [1, 2]})

    def test_mutating_the_computed_value_after_storing_does_not_change_the_cache(self):
        computed = {"alice": [1]}
        self.cache.get_or_compute("m", ("a",), None, lambda: computed)
        computed["alice"].append(2)

        cached = self.cache.get_or_compute("m", ("a",), None, self.compute)

        self.assertEqual(cached, {"alice": [1]})

    def test_clear_drops_every_entry(self):
        self.cache.get_or_compute("m", ("a",), None, lambda: "old")
        self.cache.clear()

        result = self.cache.get_or_compute("m", ("a",), None, lambda: "new")

        self.assertEqual(result, "new")


if __name__ == "__main__":
    main()
