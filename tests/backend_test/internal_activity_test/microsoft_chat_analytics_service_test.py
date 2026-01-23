from unittest import TestCase, main
from datetime import datetime, timezone
from unittest.mock import Mock, call

from backend.common.constants import (
    MICROSOFT_CHAT_MESSAGES_INDEX_KEY,
    MicrosoftChatMessagesChangeType,
)
from backend.internal_activity_service.microsoft_chat_analytics_service import (
    MicrosoftChatAnalyticsService,
)


class TestMicrosoftChatAnalyticsService(TestCase):
    def setUp(self):
        self.mock_logger = Mock()
        self.mock_redis_client = Mock()
        self.mock_date_time_util = Mock()
        self.mock_ldap_service = Mock()
        self.mock_retry_utils = Mock()

        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda func: func()

        self.service = MicrosoftChatAnalyticsService(
            logger=self.mock_logger,
            redis_client=self.mock_redis_client,
            date_time_util=self.mock_date_time_util,
            ldap_service=self.mock_ldap_service,
            retry_utils=self.mock_retry_utils,
        )

        self.start_date_str = "2024-01-01T00:00:00Z"
        self.end_date_str = "2024-01-31T23:59:59Z"
        self.start_dt_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.end_dt_utc = datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        self.start_timestamp = self.start_dt_utc.timestamp()
        self.end_timestamp = self.end_dt_utc.timestamp()

        self.mock_date_time_util.get_start_end_timestamps.return_value = (
            self.start_dt_utc,
            self.end_dt_utc,
        )

    def test_count_messages_with_ldap_list_and_date_range(self):
        ldap_list = ["user1", "user2"]
        redis_counts = [10, 20]

        mock_pipeline = Mock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = redis_counts

        result = self.service.count_microsoft_chat_messages_in_date_range(
            ldap_list=ldap_list,
            start_date=self.start_date_str,
            end_date=self.end_date_str,
        )

        self.mock_date_time_util.get_start_end_timestamps.assert_called_once_with(
            self.start_date_str, self.end_date_str
        )
        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.assert_not_called()
        self.mock_redis_client.pipeline.assert_called_once()

        expected_zcount_calls = []
        for ldap in ldap_list:
            redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
                message_status=MicrosoftChatMessagesChangeType.CREATED.value,
                sender_ldap=ldap,
            )
            expected_zcount_calls.append(
                call.zcount(redis_key, self.start_timestamp, self.end_timestamp)
            )
        mock_pipeline.zcount.assert_has_calls(expected_zcount_calls, any_order=False)
        self.assertEqual(mock_pipeline.zcount.call_count, len(ldap_list))
        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            mock_pipeline.execute
        )
        mock_pipeline.execute.assert_called_once()

        expected_result = {
            "start_date": self.start_dt_utc.isoformat(),
            "end_date": self.end_dt_utc.isoformat(),
            "result": {"user1": 10, "user2": 20},
        }
        self.assertEqual(result, expected_result)

    def test_count_messages_without_ldap_list_uses_interns_and_employees(self):
        intern_ldaps = ["intern1", "intern2"]
        employee_ldaps = ["employee1", "employee2"]
        redis_counts = [5, 15, 7, 27]

        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.return_value = (
            intern_ldaps + employee_ldaps
        )

        mock_pipeline = Mock()
        self.mock_redis_client.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = redis_counts

        result = self.service.count_microsoft_chat_messages_in_date_range(
            start_date=self.start_date_str, end_date=self.end_date_str, ldap_list=None
        )

        self.mock_ldap_service.get_all_active_interns_and_employees_ldaps.assert_called_once()

        self.mock_redis_client.pipeline.assert_called_once()
        expected_zcount_calls = []
        for ldap in intern_ldaps + employee_ldaps:
            redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
                message_status=MicrosoftChatMessagesChangeType.CREATED.value,
                sender_ldap=ldap,
            )
            expected_zcount_calls.append(
                call.zcount(redis_key, self.start_timestamp, self.end_timestamp)
            )
        mock_pipeline.zcount.assert_has_calls(expected_zcount_calls, any_order=False)
        mock_pipeline.execute.assert_called_once()

        expected_result = {
            "start_date": self.start_dt_utc.isoformat(),
            "end_date": self.end_dt_utc.isoformat(),
            "result": {
                "intern1": 5,
                "intern2": 15,
                "employee1": 7,
                "employee2": 27,
            },
        }
        self.assertEqual(result, expected_result)


if __name__ == "__main__":
    main()
