import unittest
from unittest.mock import MagicMock, call
import datetime
from backend.common.constants import CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY
from backend.frontend_service.google_chat_analytics_service import (
    GoogleChatAnalyticsService,
)


class TestGoogleChatAnalyticsService(unittest.TestCase):
    def setUp(self):
        """Set up mock objects for each test."""
        self.mock_logger = MagicMock()
        self.mock_redis_client = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.mock_date_time_util = MagicMock()
        self.mock_google_service = MagicMock()
        self.mock_ldap_service = MagicMock()

        self.service = GoogleChatAnalyticsService(
            logger=self.mock_logger,
            redis_client=self.mock_redis_client,
            retry_utils=self.mock_retry_utils,
            date_time_util=self.mock_date_time_util,
            google_service=self.mock_google_service,
            ldap_service=self.mock_ldap_service,
        )

        self.start_dt = datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc)
        self.end_dt = datetime.datetime(
            2023, 1, 31, 23, 59, 59, tzinfo=datetime.timezone.utc
        )
        self.mock_date_time_util.get_start_end_timestamps.return_value = (
            self.start_dt,
            self.end_dt,
        )

        self.mock_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = self.mock_pipeline
        self.mock_pipeline.zcount.return_value = None

    def test_count_messages_defaults_to_all_spaces_by_interns_and_employees(self):
        """Test with no space_ids or sender_ldaps provided."""
        mock_spaces = {"spaceA": "Space A Name", "spaceB": "Space B Name"}
        mock_intern_ldaps = ["intern1", "intern2"]
        mock_employee_ldaps = ["employee1", "employee2"]

        self.mock_google_service.get_chat_spaces.return_value = mock_spaces
        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.return_value = (
            mock_intern_ldaps + mock_employee_ldaps
        )
        self.mock_retry_utils.get_retry_on_transient.return_value = [
            10,
            5,
            7,
            26,
            0,
            20,
            9,
            27,
        ]
        expected_result = {
            "start_date": self.start_dt.isoformat(),
            "end_date": self.end_dt.isoformat(),
            "result": {
                "intern1": {"spaceA": 10, "spaceB": 0},
                "intern2": {"spaceA": 5, "spaceB": 20},
                "employee1": {"spaceA": 7, "spaceB": 9},
                "employee2": {"spaceA": 26, "spaceB": 27},
            },
        }

        result = self.service.count_messages(
            start_date="2023-01-01", end_date="2023-01-31"
        )

        self.mock_google_service.get_chat_spaces.assert_called_once_with(
            space_type="SPACE"
        )
        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.assert_called_once()
        self.assertEqual(result, expected_result)
        expected_zcount_calls = [
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="spaceA", sender_ldap="intern1"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="spaceA", sender_ldap="intern2"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="spaceA", sender_ldap="employee1"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="spaceA", sender_ldap="employee2"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="spaceB", sender_ldap="intern1"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="spaceB", sender_ldap="intern2"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="spaceB", sender_ldap="employee1"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="spaceB", sender_ldap="employee2"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
        ]
        self.mock_pipeline.zcount.assert_has_calls(
            expected_zcount_calls, any_order=True
        )
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            self.mock_pipeline.execute
        )

    def test_count_messages_with_specific_inputs(self):
        """Test with specific space_ids and sender_ldaps provided."""
        space_ids = ["space1", "space2"]
        sender_ldaps = ["userA", "userB"]
        self.mock_retry_utils.get_retry_on_transient.return_value = [5, 10, 15, 20]

        expected_result = {
            "start_date": self.start_dt.isoformat(),
            "end_date": self.end_dt.isoformat(),
            "result": {
                "userA": {"space1": 5, "space2": 15},
                "userB": {"space1": 10, "space2": 20},
            },
        }

        result = self.service.count_messages(
            space_ids=space_ids,
            sender_ldaps=sender_ldaps,
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.assertEqual(result, expected_result)
        self.mock_google_service.get_chat_spaces.assert_not_called()
        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.assert_not_called()

        expected_zcount_calls = [
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="space1", sender_ldap="userA"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="space1", sender_ldap="userB"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="space2", sender_ldap="userA"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="space2", sender_ldap="userB"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
        ]
        self.mock_pipeline.zcount.assert_has_calls(
            expected_zcount_calls, any_order=True
        )
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            self.mock_pipeline.execute
        )

    def test_count_messages_with_empty_and_whitespace_inputs(self):
        """Test that empty strings and strings with only whitespace are ignored."""
        space_ids_input = ["space1", " ", "space2", ""]
        sender_ldaps_input = ["userA", "", "  ", "userB"]

        space_ids_filtered = ["space1", "space2"]
        sender_ldaps_filtered = ["userA", "userB"]

        self.mock_retry_utils.get_retry_on_transient.return_value = [1, 2, 3, 4]

        expected_result = {
            "start_date": self.start_dt.isoformat(),
            "end_date": self.end_dt.isoformat(),
            "result": {
                "userA": {"space1": 1, "space2": 3},
                "userB": {"space1": 2, "space2": 4},
            },
        }

        result = self.service.count_messages(
            space_ids=space_ids_input,
            sender_ldaps=sender_ldaps_input,
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.assertEqual(result, expected_result)
        self.mock_google_service.get_chat_spaces.assert_not_called()
        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.assert_not_called()

        expected_zcount_calls = [
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="space1", sender_ldap="userA"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="space1", sender_ldap="userB"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="space2", sender_ldap="userA"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
            call(
                CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id="space2", sender_ldap="userB"
                ),
                self.start_dt.timestamp(),
                self.end_dt.timestamp(),
            ),
        ]
        self.mock_pipeline.zcount.assert_has_calls(
            expected_zcount_calls, any_order=True
        )
        self.assertEqual(
            self.mock_pipeline.zcount.call_count,
            len(space_ids_filtered) * len(sender_ldaps_filtered),
        )

    def test_count_messages_redis_returns_zero_counts(self):
        """Test when Redis pipeline returns zero for some or all counts."""
        space_ids = ["spaceX"]
        sender_ldaps = ["userC", "userD"]
        self.mock_retry_utils.get_retry_on_transient.return_value = [0, 5]

        expected_result = {
            "start_date": self.start_dt.isoformat(),
            "end_date": self.end_dt.isoformat(),
            "result": {
                "userC": {"spaceX": 0},
                "userD": {"spaceX": 5},
            },
        }

        result = self.service.count_messages(
            space_ids=space_ids,
            sender_ldaps=sender_ldaps,
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.assertEqual(result, expected_result)

    def test_count_messages_date_time_util_called_correctly(self):
        """Test that date_time_util is called with the correct arguments."""
        self.service.count_messages(
            space_ids=["s1"],
            sender_ldaps=["u1"],
            start_date="2024-03-01",
            end_date="2024-03-05",
        )
        self.mock_date_time_util.get_start_end_timestamps.assert_called_once_with(
            "2024-03-01", "2024-03-05"
        )

    def test_count_messages_empty_input_lists_cause_defaults_to_be_fetched(self):
        """Test that empty list inputs for space_ids and sender_ldaps trigger default fetching."""
        self.mock_google_service.get_chat_spaces.return_value = {"s1": "S1"}
        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.return_value = [
            "u1"
        ]
        self.mock_retry_utils.get_retry_on_transient.return_value = [10]

        expected_result = {
            "start_date": self.start_dt.isoformat(),
            "end_date": self.end_dt.isoformat(),
            "result": {"u1": {"s1": 10}},
        }

        result = self.service.count_messages(
            space_ids=[],  # Empty list
            sender_ldaps=[],  # Empty list
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.assertEqual(result, expected_result)
        self.mock_google_service.get_chat_spaces.assert_called_once()
        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.assert_called_once()

    def test_count_messages_no_messages_found_for_any(self):
        """Test case where no messages are found for any sender/space pair."""
        space_ids = ["s1", "s2"]
        sender_ldaps = ["u1", "u2"]
        self.mock_retry_utils.get_retry_on_transient.return_value = [0, 0, 0, 0]

        expected_result = {
            "start_date": self.start_dt.isoformat(),
            "end_date": self.end_dt.isoformat(),
            "result": {
                "u1": {"s1": 0, "s2": 0},
                "u2": {"s1": 0, "s2": 0},
            },
        }

        result = self.service.count_messages(
            space_ids=space_ids,
            sender_ldaps=sender_ldaps,
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.assertEqual(result, expected_result)
        self.assertEqual(self.mock_pipeline.zcount.call_count, 4)

    def test_count_messages_retry_on_transient_called(self):
        """Ensure get_retry_on_transient is used for pipeline execution."""
        space_ids = ["s1"]
        sender_ldaps = ["u1"]
        self.mock_retry_utils.get_retry_on_transient.return_value = [1]

        self.service.count_messages(
            space_ids=space_ids,
            sender_ldaps=sender_ldaps,
            start_date="2023-01-01",
            end_date="2023-01-31",
        )

        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            self.mock_pipeline.execute
        )


if __name__ == "__main__":
    unittest.main()
