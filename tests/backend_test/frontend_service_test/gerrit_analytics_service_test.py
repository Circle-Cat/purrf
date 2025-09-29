import unittest
from unittest.mock import MagicMock
from datetime import date, datetime
from backend.frontend_service.gerrit_analytics_service import GerritAnalyticsService


class TestGerritAnalyticsService(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.redis_client = MagicMock()
        self.retry_utils = MagicMock()
        self.ldap_service = MagicMock()
        self.date_time_util = MagicMock()
        self.service = GerritAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            ldap_service=self.ldap_service,
            date_time_util=self.date_time_util,
        )

    def test_get_month_buckets(self):
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)
        expected = [
            "2024-01-01_2024-01-31",
            "2024-02-01_2024-02-29",
            "2024-03-01_2024-03-31",
        ]
        self.assertEqual(self.service._get_month_buckets(start, end), expected)

    def test_get_gerrit_stats_all_time(self):
        self.ldap_service.get_active_interns_ldaps.return_value = ["user1"]

        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [
            {
                "cl_merged": "10",
                "cl_abandoned": "2",
                "cl_under_review": "1",
                "loc_merged": "150",
                "cl_reviewed": "5",
            }
        ]
        self.redis_client.pipeline.return_value = mock_pipeline
        self.retry_utils.get_retry_on_transient.side_effect = lambda func: func()

        result = self.service.get_gerrit_stats()

        expected = {
            "user1": {
                "cl_merged": 10,
                "cl_abandoned": 2,
                "cl_under_review": 1,
                "loc_merged": 150,
                "cl_reviewed": 5,
            }
        }
        self.assertEqual(result, expected)

    def test_get_gerrit_stats_monthly_with_project(self):
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [{"cl_merged": "1", "loc_merged": "50"}]
        self.date_time_util.get_start_end_timestamps.return_value = (
            datetime(2025, 4, 1),
            datetime(2025, 4, 30),
        )
        self.redis_client.pipeline.return_value = mock_pipeline
        self.retry_utils.get_retry_on_transient.side_effect = lambda func: func()

        result = self.service.get_gerrit_stats(
            ldap_list=["user1"],
            start_date_str="2024-04-01",
            end_date_str="2024-04-30",
            project_list=["test_project"],
        )
        self.assertEqual(result["user1"]["cl_merged"], 1)
        self.assertEqual(result["user1"]["loc_merged"], 50)

    def test_get_gerrit_stats_monthly_without_project(self):
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [
            {
                "cl_merged": "3",
                "cl_abandoned": "0",
                "cl_under_review": "2",
                "loc_merged": "75",
                "cl_reviewed": "1",
            }
        ]
        self.date_time_util.get_start_end_timestamps.return_value = (
            datetime(2025, 5, 1),
            datetime(2025, 8, 31),
        )

        self.redis_client.pipeline.return_value = mock_pipeline
        self.retry_utils.get_retry_on_transient.side_effect = lambda func: func()

        result = self.service.get_gerrit_stats(
            ldap_list=["user1"],
            start_date_str="2024-05-01",
            end_date_str="2024-05-31",
            project_list=None,
        )

        self.assertEqual(result["user1"]["cl_merged"], 3)
        self.assertEqual(result["user1"]["cl_abandoned"], 0)
        self.assertEqual(result["user1"]["cl_under_review"], 2)
        self.assertEqual(result["user1"]["loc_merged"], 75)
        self.assertEqual(result["user1"]["cl_reviewed"], 1)

    def test_get_gerrit_stats_without_ldap_list(self):
        self.ldap_service.get_active_interns_ldaps.return_value = {
            "user1": "User One",
            "user2": "User Two",
        }
        mock_pipeline = MagicMock()
        side_effect_data = [
            {
                "cl_merged": "4",
                "cl_abandoned": "1",
                "cl_under_review": "0",
                "loc_merged": "100",
                "cl_reviewed": "2",
            },
            {
                "cl_merged": "2",
                "cl_abandoned": "0",
                "cl_under_review": "1",
                "loc_merged": "50",
                "cl_reviewed": "3",
            },
        ]
        mock_pipeline.execute.return_value = side_effect_data
        self.redis_client.pipeline.return_value = mock_pipeline
        self.retry_utils.get_retry_on_transient.side_effect = lambda func: func()

        result = self.service.get_gerrit_stats()

        self.assertEqual(result["user1"]["cl_merged"], 4)
        self.assertEqual(result["user1"]["cl_abandoned"], 1)
        self.assertEqual(result["user1"]["loc_merged"], 100)
        self.assertEqual(result["user1"]["cl_reviewed"], 2)
        self.assertEqual(result["user2"]["cl_merged"], 2)
        self.assertEqual(result["user2"]["cl_under_review"], 1)
        self.assertEqual(result["user2"]["loc_merged"], 50)
        self.assertEqual(result["user2"]["cl_reviewed"], 3)

    def test_get_gerrit_stats_multiple_ldaps(self):
        mock_pipeline = MagicMock()
        side_effect_data = [
            {"cl_merged": "2", "loc_merged": "20"},
            {"cl_merged": "3", "loc_merged": "30"},
        ]
        mock_pipeline.execute.return_value = side_effect_data
        self.redis_client.pipeline.return_value = mock_pipeline
        self.retry_utils.get_retry_on_transient.side_effect = lambda func: func()

        result = self.service.get_gerrit_stats(
            ldap_list=["user1", "user2"],
            start_date_str=None,
            end_date_str=None,
            project_list=None,
        )

        self.assertIn("user1", result)
        self.assertIn("user2", result)

        self.assertEqual(result["user1"]["cl_merged"], 2)
        self.assertEqual(result["user1"]["loc_merged"], 20)
        self.assertEqual(result["user1"]["cl_abandoned"], 0)
        self.assertEqual(result["user1"]["cl_reviewed"], 0)
        self.assertEqual(result["user1"]["cl_under_review"], 0)

        self.assertEqual(result["user2"]["cl_merged"], 3)
        self.assertEqual(result["user2"]["loc_merged"], 30)
        self.assertEqual(result["user2"]["cl_abandoned"], 0)
        self.assertEqual(result["user2"]["cl_reviewed"], 0)
        self.assertEqual(result["user2"]["cl_under_review"], 0)


if __name__ == "__main__":
    unittest.main()
