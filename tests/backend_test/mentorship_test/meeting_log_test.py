import unittest

from backend.mentorship.meeting_log import completed_count


class TestCompletedCount(unittest.TestCase):
    def test_none_log(self):
        self.assertEqual(completed_count(None), 0)

    def test_empty_log(self):
        self.assertEqual(completed_count({}), 0)

    def test_non_dict_log(self):
        self.assertEqual(completed_count("not a dict"), 0)

    def test_null_list(self):
        self.assertEqual(completed_count({"meeting_time_list": None}), 0)

    def test_counts_manual_entries(self):
        log = {
            "meeting_time_list": [
                {"is_completed": True},
                {"is_completed": False},
            ]
        }
        self.assertEqual(completed_count(log), 1)

    def test_counts_google_entries(self):
        log = {"google_meetings": [{"is_completed": True}, {"is_completed": True}]}
        self.assertEqual(completed_count(log), 2)

    def test_sums_both_generations(self):
        log = {
            "meeting_time_list": [{"is_completed": True}],
            "google_meetings": [{"is_completed": True}, {"is_completed": False}],
        }
        self.assertEqual(completed_count(log), 2)

    def test_entry_without_is_completed_is_not_counted(self):
        log = {"meeting_time_list": [{"meeting_id": "m-1"}]}
        self.assertEqual(completed_count(log), 0)

    def test_ignores_unrelated_keys(self):
        log = {"some_future_key": [{"is_completed": True}]}
        self.assertEqual(completed_count(log), 0)

    def test_non_dict_entries_are_skipped(self):
        log = {
            "meeting_time_list": [None, "junk", 42, {"is_completed": True}],
            "google_meetings": [["nested"], {"is_completed": True}],
        }
        self.assertEqual(completed_count(log), 2)


if __name__ == "__main__":
    unittest.main()
