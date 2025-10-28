from unittest import TestCase, main
from unittest.mock import patch, Mock
from datetime import datetime, timezone, timedelta, date

from backend.utils.date_time_util import DateTimeUtil


class TestDateTimeUtil(TestCase):
    def setUp(self):
        self.logger = Mock()
        self.utils = DateTimeUtil(logger=self.logger)
        self.test_cases_format_datetime_to_iso_utc_z = [
            (
                datetime(2023, 10, 27, 10, 30, 45, 123456, tzinfo=timezone.utc),
                "2023-10-27T10:30:45.123456Z",
            ),
            (
                datetime(2023, 10, 27, 10, 30, 45, 123456),
                "2023-10-27T10:30:45.123456",
            ),
        ]

        self.test_date_valid_dates_parse_date_to_utc_datetime = [
            # Case 1: Normal month, start of day
            (
                "2023-10-27",
                True,
                datetime(2023, 10, 27, 0, 0, 0, 0, tzinfo=timezone.utc),
            ),
            # Case 2: Normal month, end of day
            (
                "2023-10-27",
                False,
                datetime(2023, 10, 27, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 3: Month with 30 days, start of day
            (
                "2023-09-15",
                True,
                datetime(2023, 9, 15, 0, 0, 0, 0, tzinfo=timezone.utc),
            ),
            # Case 4: Month with 30 days, end of day
            (
                "2023-09-30",
                False,
                datetime(2023, 9, 30, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 5: February, non-leap year, start of day
            (
                "2023-02-10",
                True,
                datetime(2023, 2, 10, 0, 0, 0, 0, tzinfo=timezone.utc),
            ),
            # Case 6: February, non-leap year, end of day
            (
                "2023-02-28",
                False,
                datetime(2023, 2, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 7: February, leap year, start of day
            (
                "2024-02-15",
                True,
                datetime(2024, 2, 15, 0, 0, 0, 0, tzinfo=timezone.utc),
            ),
            # Case 8: February, leap year, end of day
            (
                "2024-02-29",
                False,
                datetime(2024, 2, 29, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 9: Edge case - Year change, start of day
            (
                "2023-12-31",
                True,
                datetime(2023, 12, 31, 0, 0, 0, 0, tzinfo=timezone.utc),
            ),
            # Case 10: Edge case - Year change, end of day
            (
                "2024-01-01",
                False,
                datetime(2024, 1, 1, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 11: Edge case - Empty string
            ("", True, None),
            # Case 12: Edge case - None
            (None, True, None),
        ]

        self.test_invalid_formats_parse_date_to_utc_datetime = [
            ("27-10-2023", True),
            ("2023/10/27", True),
            ("October 27, 2023", True),
        ]

        self.fixed_now = datetime(2024, 6, 28, 15, 30, 0, tzinfo=timezone.utc)

        self.test_cases_get_start_end_timestamps = [
            # Case 1: both dates provided, normal range within past dates
            (
                "2024-05-01",
                "2024-06-01",
                datetime(2024, 5, 1, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 1, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 2: only start_date provided, start less than one month ago
            (
                "2024-05-15",
                None,
                datetime(2024, 5, 15, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 15, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 3: only end_date provided, end date before today
            (
                None,
                "2024-06-20",
                datetime(2024, 5, 20, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 20, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 4: neither provided, use now - 1 month
            (
                None,
                None,
                datetime(2024, 5, 28, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 5: only start_date provided, when is less than a month ago
            (
                "2024-06-15",
                None,
                datetime(2024, 6, 15, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 6: both dates provided, but end date is in the future
            (
                "2024-05-01",
                "2024-07-01",
                datetime(2024, 5, 1, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 7: start_date and end_date are the same day
            (
                "2024-06-10",
                "2024-06-10",
                datetime(2024, 6, 10, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 10, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 8: only start_date is today
            (
                "2024-06-28",
                None,
                datetime(2024, 6, 28, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 9: only end_date is today
            (
                None,
                "2024-06-28",
                datetime(2024, 5, 28, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 10: only end_date, and it is in the future
            (
                None,
                "2025-07-28",
                datetime(2024, 5, 28, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 11: start_date and end_date covering a full calendar month
            (
                "2024-05-01",
                "2024-05-31",
                datetime(2024, 5, 1, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 5, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 12: start_date in a non-leap year January,
            (
                "2023-01-29",
                None,
                datetime(2023, 1, 29, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2023, 2, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
            # Case 13: start_date in a leap year January
            (
                "2024-01-29",
                None,
                datetime(2024, 1, 29, 0, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 2, 29, 23, 59, 59, 999999, tzinfo=timezone.utc),
            ),
        ]

        self.test_invalid_cases_get_start_end_timestamps = [
            # Case 1: end_date earlier than start_date
            (
                "2024-06-01",
                "2024-02-01",
            ),
            # Case 2: start_date is in the future
            (
                "2030-01-01",
                "2030-01-02",
            ),
            # Case 3: only start_date, and it is in the future
            (
                "2030-01-01",
                None,
            ),
            # Case 4: end_date is invalid format
            (
                "2024-05-01",
                "2024-31-12",
            ),
            # Case 5: start_date is invalid format
            (
                "2024/05/01",
                "2024-06-01",
            ),
            # Case 6: both dates invalid format
            (
                "2024-99-99",
                "abcd-ef-gh",
            ),
        ]

        self.test_cases_compute_buckets_weekly = [
            # Case 1: 2025-10-21 (Tuesday) -> Week range 2025-10-20 (Monday) to 2025-10-26 (Sunday)
            ("2025-10-21 14:30:00.123456", "2025-10-20_2025-10-26"),
            # Case 2: 2025-10-30 (Thursday) -> Cross-month week range 2025-10-27 (Monday) to 2025-11-02 (Sunday)
            ("2025-10-30 08:00:00", "2025-10-27_2025-11-02"),
            # Case 3: 2025-01-06 (Monday) -> Monday input should start from itself
            ("2025-01-06 00:00:01", "2025-01-06_2025-01-12"),
            # Case 4: 2025-01-12 (Sunday) -> Sunday input should end on itself
            ("2025-01-12 23:59:59", "2025-01-06_2025-01-12"),
            # Case 5: Cross-year test (2025-12-31 is Tuesday) -> Week range 2025-12-29 (Monday) to 2026-01-04 (Sunday)
            ("2025-12-31 12:00:00", "2025-12-29_2026-01-04"),
            # Case 6: Leap year test (2024-02-29 is Thursday) -> Week range 2024-02-26 (Monday) to 2024-03-03 (Sunday)
            ("2024-02-29 12:00:00", "2024-02-26_2024-03-03"),
            # Case 7: Test with datetime object directly - Tuesday
            (datetime(2025, 10, 21, 14, 30, 0, 123456), "2025-10-20_2025-10-26"),
            # Case 8: Test with datetime object directly - Monday
            (datetime(2025, 1, 6, 0, 0, 1), "2025-01-06_2025-01-12"),
            # Case 9: Test with datetime object directly - Sunday
            (datetime(2025, 1, 12, 23, 59, 59), "2025-01-06_2025-01-12"),
            # Case 10: Unix timestamp for 2025-10-21 14:30:00 UTC (matches Case 1)
            (1761028200, "2025-10-20_2025-10-26"),
        ]

        self.test_invalid_cases_compute_buckets_weekly = [
            (
                "2025/10/21 14:30:00",
                "Invalid string format (uses / instead of -)",
                ValueError,
            ),
            ("Just a string", "Non-date string", ValueError),
            ("", "Empty string", ValueError),
            ([1, 2, 3], "List input", TypeError),
            (None, "None input", TypeError),
            (1.0, "Float input", TypeError),
        ]

        self.test_cases_parse_timestamp_without_microseconds_valid = [
            (
                "2023-10-27 10:30:45.123456",
                datetime(2023, 10, 27, 10, 30, 45),
            ),
            (
                "2023-10-28 11:00:00",
                datetime(2023, 10, 28, 11, 0, 0),
            ),
            (
                "1999-01-01 00:00:00.999",
                datetime(1999, 1, 1, 0, 0, 0),
            ),
            (
                "2025-12-31 23:59:59",
                datetime(2025, 12, 31, 23, 59, 59),
            ),
        ]

        self.test_cases_parse_timestamp_without_microseconds_invalid = [
            ("2023/10/27 10:30:45.123", "Incorrect date separator"),
            ("27-10-2023 10:30:45", "Incorrect date order"),
            ("2023-10-27T10:30:45", "Incorrect date-time separator"),
            ("Invalid Timestamp String", "Completely invalid string"),
            ("", "Empty string"),
            ("2023-10-27 10:30", "Missing seconds"),
            ("2023-10-27", "Missing time part"),
            ("2023-10-27 25:00:00", "Invalid hour"),
            ("2023-13-01 00:00:00", "Invalid month"),
            (None, "None input"),
        ]

        self.test_cases_get_week_buckets = [
            # Case 1: Single week (start=Monday, end=Sunday)
            (
                date(2024, 6, 24),  # 2024-06-24 (Monday)
                date(2024, 6, 30),  # 2024-06-30 (Sunday)
                ["2024-06-24_2024-06-30"],  # Expected 1 weekly bucket
            ),
            # Case 2: Cross two weeks (start=Wednesday, end=next Tuesday)
            (
                date(2024, 7, 3),  # 2024-07-03 (Wednesday)
                date(2024, 7, 9),  # 2024-07-09 (Tuesday)
                [
                    "2024-07-01_2024-07-07",  # Week 1 (covers 7.3-7.5)
                    "2024-07-08_2024-07-14",  # Week 2 (covers 7.6-7.9)
                ],
            ),
            # Case 3: Cross month (start=last day of June, end=first day of July)
            (
                date(2024, 6, 30),  # 2024-06-30 (Sunday)
                date(2024, 7, 1),  # 2024-07-01 (Monday)
                [
                    "2024-06-24_2024-06-30",  # Last week of June
                    "2024-07-01_2024-07-07",  # First week of July (includes 7.1)
                ],
            ),
            # Case 4: Cross year (start=last day of 2024, end=first day of 2025)
            (
                date(2024, 12, 31),  # 2024-12-31 (Tuesday)
                date(2025, 1, 2),  # 2025-01-02 (Thursday)
                [
                    "2024-12-30_2025-01-05",  # Single week covering cross-year dates
                ],
            ),
            # Case 5: Start equals end (single day, Wednesday)
            (
                date(2024, 8, 14),  # 2024-08-14 (Wednesday)
                date(2024, 8, 14),  # 2024-08-14 (Wednesday)
                ["2024-08-12_2024-08-18"],  # Weekly bucket containing the day
            ),
            # Case 6: Full month (February 2024, leap year)
            (
                date(2024, 2, 1),  # 2024-02-01 (Thursday)
                date(2024, 2, 29),  # 2024-02-29 (Thursday)
                [
                    "2024-01-29_2024-02-04",  # Week 1 (covers 2.1-2.4)
                    "2024-02-05_2024-02-11",  # Week 2
                    "2024-02-12_2024-02-18",  # Week 3
                    "2024-02-19_2024-02-25",  # Week 4
                    "2024-02-26_2024-03-03",  # Week 5 (covers 2.26-2.29)
                ],
            ),
        ]

        self.test_invalid_cases_get_week_buckets = [
            # Case 1: start=2024-07-10, end=2024-07-01 (start is later than end)
            (date(2024, 7, 10), date(2024, 7, 1)),
            # Case 2: start=2025-01-01, end=2024-12-31 (cross-year reverse order)
            (date(2025, 1, 1), date(2024, 12, 31)),
        ]

    def test_get_week_buckets_valid_cases(self):
        """Test get_week_buckets method with valid scenarios (data-driven)."""
        for i, (start_date, end_date, expected_buckets) in enumerate(
            self.test_cases_get_week_buckets
        ):
            with self.subTest(
                case=f"Get Week Buckets Valid Case {i + 1}: "
                f"start={start_date}, end={end_date}"
            ):
                actual_buckets = self.utils.get_week_buckets(start_date, end_date)
                # Verify the number of weekly buckets matches
                self.assertEqual(
                    len(actual_buckets),
                    len(expected_buckets),
                    msg=f"Bucket count mismatch: expected {len(expected_buckets)}, got {len(actual_buckets)}",
                )
                # Verify the content of weekly buckets matches
                self.assertListEqual(
                    actual_buckets,
                    expected_buckets,
                    msg=f"Bucket content mismatch: expected {expected_buckets}, got {actual_buckets}",
                )

    def test_get_week_buckets_invalid_cases(self):
        """Test get_week_buckets method with invalid scenarios (start > end, expects ValueError)."""
        for i, (start_date, end_date) in enumerate(
            self.test_invalid_cases_get_week_buckets
        ):
            with self.subTest(
                case=f"Get Week Buckets Invalid Case {i + 1}: "
                f"start={start_date} (later than) end={end_date}"
            ):
                with self.assertRaises(ValueError) as ctx:
                    self.utils.get_week_buckets(start_date, end_date)
                # Verify the error message contains key hint
                self.assertIn(
                    f"start_date ({start_date}) must be <= end_date ({end_date})",
                    str(ctx.exception),
                )

    def test_parse_timestamp_without_microseconds_valid_input(self):
        """Tests the parse_timestamp_without_microseconds method with valid timestamp strings."""
        for i, (timestamp_str, expected_dt) in enumerate(
            self.test_cases_parse_timestamp_without_microseconds_valid
        ):
            with self.subTest(f"Valid case {i + 1}: '{timestamp_str}'"):
                result = self.utils.parse_timestamp_without_microseconds(timestamp_str)
                self.assertEqual(result, expected_dt)

    def test_parse_timestamp_without_microseconds_invalid_input(self):
        """
        Tests the parse_timestamp_without_microseconds method with invalid timestamp strings,
        expecting a ValueError to be raised.
        """
        for i, (timestamp_str, description) in enumerate(
            self.test_cases_parse_timestamp_without_microseconds_invalid
        ):
            with self.subTest(
                f"Invalid case {i + 1}: '{timestamp_str}' ({description})"
            ):
                with self.assertRaises(ValueError):
                    self.utils.parse_timestamp_without_microseconds(timestamp_str)

    def test_compute_buckets_weekly(self):
        """Test the weekly aggregation logic to ensure correct Monday-Sunday range keys."""
        for i, (input_timestamp, expected_key) in enumerate(
            self.test_cases_compute_buckets_weekly
        ):
            with self.subTest(
                case=f"Weekly Case {i + 1}: Input {input_timestamp} -> Expected {expected_key}"
            ):
                actual_key = self.utils.compute_buckets_weekly(input_timestamp)
                self.assertEqual(actual_key, expected_key)

    def test_compute_buckets_weekly_invalid_input(self):
        """Test that invalid timestamps now raise the correct exception (ValueError for bad format, TypeError for unsupported types)."""
        for i, (input_timestamp, description, expected_exception) in enumerate(
            self.test_invalid_cases_compute_buckets_weekly
        ):
            with self.subTest(
                case=f"Invalid Weekly Case {i + 1}: Input '{input_timestamp}' ({description})"
            ):
                with self.assertRaises(expected_exception):
                    self.utils.compute_buckets_weekly(input_timestamp)

    def test_format_datetime_to_iso_utc_z_valid_inputs(self):
        for i, (date_str, expected_dt) in enumerate(
            self.test_cases_format_datetime_to_iso_utc_z
        ):
            with self.subTest(case=f"Valid Date Case {i + 1}: {date_str}"):
                actual_dt = self.utils.format_datetime_to_iso_utc_z(date_str)
                self.assertEqual(actual_dt, expected_dt)

    def test_parse_date_to_utc_datetime_valid_inputs(self):
        for i, (date_str, start_of_day, expected_dt) in enumerate(
            self.test_date_valid_dates_parse_date_to_utc_datetime
        ):
            with self.subTest(
                case=f"Valid Date Case {i + 1}: {date_str}, start_of_day={start_of_day}"
            ):
                actual_dt = self.utils.parse_date_to_utc_datetime(
                    date_str, start_of_day=start_of_day
                )
                self.assertEqual(actual_dt, expected_dt)

    def test_parse_date_to_utc_datetime_invalid_format(self):
        for i, (date_str, start_of_day) in enumerate(
            self.test_invalid_formats_parse_date_to_utc_datetime
        ):
            with self.subTest(case=f"Invalid Format Case {i + 1}: '{date_str}'"):
                with self.assertRaises(ValueError):
                    self.utils.parse_date_to_utc_datetime(
                        date_str, start_of_day=start_of_day
                    )

    @patch("backend.utils.date_time_util.datetime")
    def test_get_start_end_timestamps(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_now
        mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(
            *args, **kwargs
        )
        mock_datetime.timezone = timezone
        mock_datetime.replace = datetime.replace
        for i, (start_str, end_str, expected_start, expected_end) in enumerate(
            self.test_cases_get_start_end_timestamps
        ):
            with self.subTest(
                case=f"Case {i + 1} - start: {start_str}, end: {end_str}"
            ):
                start_dt, end_dt = self.utils.get_start_end_timestamps(
                    start_str, end_str
                )
                self.assertEqual(start_dt, expected_start)
                self.assertEqual(end_dt, expected_end)

    @patch("backend.utils.date_time_util.datetime")
    def test_get_start_end_timestamps_invalid_inputs(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_now
        mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(
            *args, **kwargs
        )
        mock_datetime.timezone = timezone
        mock_datetime.replace = datetime.replace

        for i, (start_str, end_str) in enumerate(
            self.test_invalid_cases_get_start_end_timestamps
        ):
            with self.subTest(
                case=f"Case {i + 1} - start: {start_str}, end: {end_str}"
            ):
                with self.assertRaises(ValueError):
                    self.utils.get_start_end_timestamps(start_str, end_str)

    def test_format_datetime_str_to_int(self):
        date_str = "2023-07-12T14:35:22.123+0000"
        expected_int = 20230712
        result = self.utils.format_datetime_str_to_int(date_str)
        self.assertEqual(result, expected_int)

    def test_format_datetime_str_to_int_invalid_format(self):
        with self.assertRaises(ValueError):
            self.utils.format_datetime_str_to_int("2023-07-12 14:35:22")

    def test_format_datetime_to_int(self):
        dt = datetime(2023, 7, 12, 14, 35, 22)
        expected_int = 20230712
        result = self.utils.format_datetime_to_int(dt)
        self.assertEqual(result, expected_int)

    def test_resolve_start_end_timestamps_defaults_to_previous_day(self):
        now = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        yesterday = now - timedelta(days=1)

        time_min, time_max = self.utils.resolve_start_end_timestamps()

        self.assertEqual(time_max, now.isoformat().replace("+00:00", "Z"))
        self.assertEqual(time_min, yesterday.isoformat().replace("+00:00", "Z"))

    def test_resolve_start_end_timestamps_with_explicit_dates(self):
        start_date = "2023-09-01"
        end_date = "2023-09-03"

        time_min, time_max = self.utils.resolve_start_end_timestamps(
            start_date, end_date
        )

        self.assertTrue(time_min.startswith("2023-09-01T"))
        self.assertTrue(time_max.startswith("2023-09-03T"))
        self.assertTrue(time_min.endswith("Z"))
        self.assertTrue(time_max.endswith("Z"))


if __name__ == "__main__":
    main()
