from unittest import TestCase, main
from unittest.mock import patch, Mock
from datetime import datetime, timezone

from backend.utils.date_time_util import (
    parse_date_to_utc_datetime,
    get_start_end_timestamps,
    DateTimeUtil,
)


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


class TestDateTimeParser(TestCase):
    TEST_DATA_VALID_DATES_PARSE_DATE_TO_UTC_DATETIME = [
        # Case 1: Normal month, start of day
        ("2023-10-27", True, datetime(2023, 10, 27, 0, 0, 0, 0, tzinfo=timezone.utc)),
        # Case 2: Normal month, end of day
        (
            "2023-10-27",
            False,
            datetime(2023, 10, 27, 23, 59, 59, 999999, tzinfo=timezone.utc),
        ),
        # Case 3: Month with 30 days, start of day
        ("2023-09-15", True, datetime(2023, 9, 15, 0, 0, 0, 0, tzinfo=timezone.utc)),
        # Case 4: Month with 30 days, end of day
        (
            "2023-09-30",
            False,
            datetime(2023, 9, 30, 23, 59, 59, 999999, tzinfo=timezone.utc),
        ),
        # Case 5: February, non-leap year, start of day
        ("2023-02-10", True, datetime(2023, 2, 10, 0, 0, 0, 0, tzinfo=timezone.utc)),
        # Case 6: February, non-leap year, end of day
        (
            "2023-02-28",
            False,
            datetime(2023, 2, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
        ),
        # Case 7: February, leap year, start of day
        ("2024-02-15", True, datetime(2024, 2, 15, 0, 0, 0, 0, tzinfo=timezone.utc)),
        # Case 8: February, leap year, end of day
        (
            "2024-02-29",
            False,
            datetime(2024, 2, 29, 23, 59, 59, 999999, tzinfo=timezone.utc),
        ),
        # Case 9: Edge case - Year change, start of day
        ("2023-12-31", True, datetime(2023, 12, 31, 0, 0, 0, 0, tzinfo=timezone.utc)),
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

    TEST_INVALID_FORMATS_PARSE_DATE_TO_UTC_DATETIME = [
        ("27-10-2023", True),
        ("2023/10/27", True),
        ("October 27, 2023", True),
    ]

    FIXED_NOW = datetime(2024, 6, 28, 15, 30, 0, tzinfo=timezone.utc)

    TEST_CASES_GET_START_END_TIMESTAMPS = [
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

    TEST_INVALID_CASES_GET_START_END_TIMESTAMPS = [
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

    def test_parse_date_to_utc_datetime_valid_inputs(self):
        for i, (date_str, start_of_day, expected_dt) in enumerate(
            self.TEST_DATA_VALID_DATES_PARSE_DATE_TO_UTC_DATETIME
        ):
            with self.subTest(
                case=f"Valid Date Case {i + 1}: {date_str}, start_of_day={start_of_day}"
            ):
                actual_dt = parse_date_to_utc_datetime(
                    date_str, start_of_day=start_of_day
                )
                self.assertEqual(actual_dt, expected_dt)

    def test_parse_date_to_utc_datetime_invalid_format(self):
        for i, (date_str, start_of_day) in enumerate(
            self.TEST_INVALID_FORMATS_PARSE_DATE_TO_UTC_DATETIME
        ):
            with self.subTest(case=f"Invalid Format Case {i + 1}: '{date_str}'"):
                with self.assertRaises(ValueError):
                    parse_date_to_utc_datetime(date_str, start_of_day=start_of_day)

    @patch("backend.utils.date_time_util.datetime")
    def test_get_start_end_timestamps(self, mock_datetime):
        mock_datetime.now.return_value = self.FIXED_NOW
        mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(
            *args, **kwargs
        )
        mock_datetime.timezone = timezone
        mock_datetime.replace = datetime.replace
        for i, (start_str, end_str, expected_start, expected_end) in enumerate(
            self.TEST_CASES_GET_START_END_TIMESTAMPS
        ):
            with self.subTest(
                case=f"Case {i + 1} - start: {start_str}, end: {end_str}"
            ):
                start_dt, end_dt = get_start_end_timestamps(start_str, end_str)
                self.assertEqual(start_dt, expected_start)
                self.assertEqual(end_dt, expected_end)

    @patch("backend.utils.date_time_util.datetime")
    def test_get_start_end_timestamps_invalid_inputs(self, mock_datetime):
        mock_datetime.now.return_value = self.FIXED_NOW
        mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(
            *args, **kwargs
        )
        mock_datetime.timezone = timezone
        mock_datetime.replace = datetime.replace

        for i, (start_str, end_str) in enumerate(
            self.TEST_INVALID_CASES_GET_START_END_TIMESTAMPS
        ):
            with self.subTest(
                case=f"Case {i + 1} - start: {start_str}, end: {end_str}"
            ):
                with self.assertRaises(ValueError):
                    get_start_end_timestamps(start_str, end_str)


if __name__ == "__main__":
    main()
