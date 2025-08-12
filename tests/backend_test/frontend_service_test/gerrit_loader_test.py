import unittest
from unittest.mock import patch, MagicMock
from datetime import date
from backend.frontend_service import gerrit_loader


class TestGerritLoader(unittest.TestCase):
    def test_get_month_buckets(self):
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)
        expected = [
            "2024-01-01_2024-01-31",
            "2024-02-01_2024-02-29",
            "2024-03-01_2024-03-31",
        ]
        self.assertEqual(gerrit_loader.get_month_buckets(start, end), expected)

    def test_parse_date(self):
        self.assertEqual(gerrit_loader.parse_date("2024-06-10"), date(2024, 6, 10))

    def test_parse_date_invalid(self):
        with self.assertRaises(ValueError):
            gerrit_loader.parse_date("06/10/2024")

    def test_parse_date_none(self):
        self.assertIsNone(gerrit_loader.parse_date(None))

    @patch("backend.frontend_service.gerrit_loader.RedisClientFactory")
    @patch("backend.frontend_service.gerrit_loader.get_all_active_ldap_users")
    def test_get_gerrit_stats_all_time(self, mock_get_ldaps, mock_redis_factory):
        mock_get_ldaps.return_value = {"user1": "Alice"}
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.hgetall.return_value = {
            "cl_merged": "10",
            "cl_abandoned": "2",
            "cl_under_review": "1",
            "loc_merged": "150",
            "cl_reviewed": "5",
        }
        mock_pipeline.execute.return_value = [mock_pipeline.hgetall.return_value]
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        result = gerrit_loader.get_gerrit_stats()

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

    @patch("backend.frontend_service.gerrit_loader.RedisClientFactory")
    def test_get_gerrit_stats_monthly_with_project(self, mock_redis_factory):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.hgetall.return_value = {"cl_merged": "1", "loc_merged": "50"}
        mock_pipeline.execute.return_value = [mock_pipeline.hgetall.return_value]
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        result = gerrit_loader.get_gerrit_stats(
            raw_ldap="user1",
            start_date_str="2024-04-01",
            end_date_str="2024-04-30",
            raw_project="test_project",
        )
        self.assertEqual(result["user1"]["cl_merged"], 1)
        self.assertEqual(result["user1"]["loc_merged"], 50)

    @patch("backend.frontend_service.gerrit_loader.RedisClientFactory")
    def test_get_gerrit_stats_monthly_without_project(self, mock_redis_factory):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.hgetall.return_value = {
            "cl_merged": "3",
            "cl_abandoned": "0",
            "cl_under_review": "2",
            "loc_merged": "75",
            "cl_reviewed": "1",
        }
        mock_pipeline.execute.return_value = [mock_pipeline.hgetall.return_value]
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        result = gerrit_loader.get_gerrit_stats(
            raw_ldap="user1",
            start_date_str="2024-05-01",
            end_date_str="2024-05-31",
            raw_project=None,
        )

        self.assertEqual(result["user1"]["cl_merged"], 3)
        self.assertEqual(result["user1"]["cl_abandoned"], 0)
        self.assertEqual(result["user1"]["cl_under_review"], 2)
        self.assertEqual(result["user1"]["loc_merged"], 75)
        self.assertEqual(result["user1"]["cl_reviewed"], 1)

    @patch("backend.frontend_service.gerrit_loader.get_all_active_ldap_users")
    @patch("backend.frontend_service.gerrit_loader.RedisClientFactory")
    def test_get_gerrit_stats_without_ldap_list(
        self, mock_redis_factory, mock_get_all_ldaps
    ):
        mock_get_all_ldaps.return_value = {"user1": "User One", "user2": "User Two"}

        mock_redis = MagicMock()
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
        mock_pipeline.hgetall.side_effect = side_effect_data
        mock_pipeline.execute.return_value = side_effect_data
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        result = gerrit_loader.get_gerrit_stats()

        self.assertEqual(result["user1"]["cl_merged"], 4)
        self.assertEqual(result["user1"]["cl_abandoned"], 1)
        self.assertEqual(result["user1"]["loc_merged"], 100)
        self.assertEqual(result["user1"]["cl_reviewed"], 2)
        self.assertEqual(result["user2"]["cl_merged"], 2)
        self.assertEqual(result["user2"]["cl_under_review"], 1)
        self.assertEqual(result["user2"]["loc_merged"], 50)
        self.assertEqual(result["user2"]["cl_reviewed"], 3)

    @patch("backend.frontend_service.gerrit_loader.RedisClientFactory")
    def test_get_gerrit_stats_multiple_ldaps(self, mock_redis_factory):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        side_effect_data = [
            {"cl_merged": "2", "loc_merged": "20"},
            {"cl_merged": "3", "loc_merged": "30"},
        ]
        mock_pipeline.execute.return_value = side_effect_data
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis_factory.return_value.create_redis_client.return_value = mock_redis

        result = gerrit_loader.get_gerrit_stats(
            raw_ldap="user1,user2",
            start_date_str=None,
            end_date_str=None,
            raw_project=None,
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
