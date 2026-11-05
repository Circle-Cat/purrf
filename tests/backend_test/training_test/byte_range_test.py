"""Reading a Range header, and working out which bytes it names."""

import unittest

from backend.training.byte_range import (
    RangeSpec,
    parse_range_header,
    resolve_range,
)

# The mentee onboarding package ships a video this size; ranges over it are
# the whole reason this module exists.
_VIDEO_SIZE = 3697276


class TestParseRangeHeader(unittest.TestCase):
    def test_no_header_asks_for_the_whole_object(self):
        self.assertIsNone(parse_range_header(None))
        self.assertIsNone(parse_range_header(""))

    def test_a_bounded_range_keeps_both_ends(self):
        self.assertEqual(parse_range_header("bytes=100-199"), RangeSpec(100, 199))

    def test_an_open_ended_range_keeps_only_its_start(self):
        """This is what Safari opens a video with."""
        self.assertEqual(parse_range_header("bytes=0-"), RangeSpec(first=0))
        self.assertEqual(parse_range_header("bytes=500-"), RangeSpec(first=500))

    def test_a_leading_dash_asks_for_the_last_bytes_not_the_first(self):
        """`bytes=-8` is the final eight bytes, which is how a player finds an
        MP4 index written at the end of the file."""
        self.assertEqual(parse_range_header("bytes=-8"), RangeSpec(suffix_length=8))

    def test_a_single_byte_range_is_a_range(self):
        self.assertEqual(parse_range_header("bytes=0-0"), RangeSpec(0, 0))

    def test_the_unit_is_matched_regardless_of_case(self):
        self.assertEqual(parse_range_header("BYTES=0-9"), RangeSpec(0, 9))

    def test_surrounding_whitespace_does_not_hide_the_range(self):
        self.assertEqual(parse_range_header("  bytes=0-9 "), RangeSpec(0, 9))

    def test_several_ranges_at_once_are_declined_rather_than_refused(self):
        """Answering them means a multipart body no course player asks for, so
        the header is ignored and the caller serves the whole object."""
        self.assertIsNone(parse_range_header("bytes=0-99,200-299"))

    def test_an_end_before_the_start_makes_the_header_invalid_not_an_error(self):
        """Invalid is about the header and is ignored; unsatisfiable is about
        the object and is a 416. This one is the former."""
        self.assertIsNone(parse_range_header("bytes=200-100"))

    def test_a_malformed_header_is_ignored(self):
        for value in [
            "bytes=",
            "bytes=-",
            "bytes=abc-def",
            "bytes=1.5-2",
            "items=0-10",
            "0-10",
            "bytes=0-10; charset=utf-8",
            "bytes=-1-2",
        ]:
            with self.subTest(value=value):
                self.assertIsNone(parse_range_header(value))

    def test_digits_python_cannot_parse_are_not_read_as_numbers(self):
        """A regex written with \\d would match these and then fail on int()."""
        self.assertIsNone(parse_range_header("bytes=٠-٩"))
        self.assertIsNone(parse_range_header("bytes=0-²"))


class TestResolveRange(unittest.TestCase):
    def test_a_bounded_range_keeps_both_ends_inclusive(self):
        resolved = resolve_range(RangeSpec(100, 199), _VIDEO_SIZE)

        self.assertEqual((resolved.start, resolved.end), (100, 199))
        self.assertEqual(resolved.length, 100)
        self.assertEqual(resolved.total, _VIDEO_SIZE)

    def test_an_open_ended_range_runs_to_the_last_byte(self):
        resolved = resolve_range(RangeSpec(first=10), 100)

        self.assertEqual((resolved.start, resolved.end), (10, 99))

    def test_a_suffix_range_counts_back_from_the_end(self):
        resolved = resolve_range(RangeSpec(suffix_length=10), 100)

        self.assertEqual((resolved.start, resolved.end), (90, 99))
        self.assertEqual(resolved.length, 10)

    def test_a_suffix_longer_than_the_object_is_the_whole_object(self):
        resolved = resolve_range(RangeSpec(suffix_length=5000), 100)

        self.assertEqual((resolved.start, resolved.end), (0, 99))

    def test_an_end_past_the_last_byte_is_clamped_not_refused(self):
        """Reading ahead past the end is what a media element does before it
        knows how long the file is."""
        resolved = resolve_range(RangeSpec(0, 10_000_000), _VIDEO_SIZE)

        self.assertEqual((resolved.start, resolved.end), (0, _VIDEO_SIZE - 1))
        self.assertEqual(resolved.length, _VIDEO_SIZE)

    def test_a_start_past_the_last_byte_cannot_be_satisfied(self):
        self.assertIsNone(resolve_range(RangeSpec(first=100), 100))
        self.assertIsNone(resolve_range(RangeSpec(200, 300), 100))

    def test_the_last_byte_alone_is_satisfiable(self):
        resolved = resolve_range(RangeSpec(first=99), 100)

        self.assertEqual((resolved.start, resolved.end), (99, 99))

    def test_a_suffix_of_nothing_cannot_be_satisfied(self):
        self.assertIsNone(resolve_range(RangeSpec(suffix_length=0), 100))

    def test_an_empty_object_satisfies_no_range_at_all(self):
        self.assertIsNone(resolve_range(RangeSpec(first=0), 0))
        self.assertIsNone(resolve_range(RangeSpec(suffix_length=10), 0))

    def test_content_range_names_the_bytes_and_the_whole_size(self):
        resolved = resolve_range(RangeSpec(0, 1), _VIDEO_SIZE)

        self.assertEqual(resolved.content_range(), f"bytes 0-1/{_VIDEO_SIZE}")


if __name__ == "__main__":
    unittest.main()
