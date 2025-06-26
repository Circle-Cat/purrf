import unittest
from unittest.mock import patch, Mock
from src.frontend_service.chat_query_utils import count_messages_in_date_range


class TestCountMessagesInDateRange(unittest.TestCase):
    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_single_space_single_sender(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = [3]
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-31",
            space_ids=["space1"],
            sender_ldaps=["admin"],
        )
        self.assertEqual(result["admin"]["space1"], 3)
        mock_pipeline.zcount.assert_called_once()
        mock_pipeline.execute.assert_called_once()

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_key_exists_but_zero_count(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = [0]
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-31",
            space_ids=["spaceX"],
            sender_ldaps=["admin"],
        )
        self.assertEqual(result["admin"]["spaceX"], 0)

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_key_does_not_exist(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = [0]
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-31",
            space_ids=["nonexistent_space"],
            sender_ldaps=["ghost"],
        )
        self.assertEqual(result["ghost"]["nonexistent_space"], 0)

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_multiple_spaces_and_senders(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_pipeline = Mock()
        # Pipeline returns results in order:
        # [space1/admin, space1/bob, space2/admin, space2/bob]
        mock_pipeline.execute.return_value = [2, 0, 0, 1]
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-31",
            space_ids=["space1", "space2"],
            sender_ldaps=["admin", "bob"],
        )

        expected = {
            "admin": {"space1": 2, "space2": 0},
            "bob": {"space1": 0, "space2": 1},
        }
        self.assertEqual(result, expected)
        # Verify pipeline was used with 4 queries (2 spaces × 2 senders)
        self.assertEqual(mock_pipeline.zcount.call_count, 4)
        mock_pipeline.execute.assert_called_once()

    def test_invalid_date_format(self):
        with self.assertRaises(ValueError):
            count_messages_in_date_range(
                start_date="invalid-date",
                end_date="2025-01-31",
                space_ids=["space1"],
                sender_ldaps=["admin"],
            )

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_default_dates(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = [5]
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date=None, end_date=None, space_ids=["space1"], sender_ldaps=["admin"]
        )
        self.assertIn("admin", result)
        self.assertEqual(result["admin"]["space1"], 5)

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    @patch("src.frontend_service.chat_query_utils.get_chat_spaces")
    @patch("src.frontend_service.chat_query_utils.get_all_ldaps_and_displaynames")
    def test_fallback_to_all_spaces_and_microsoft_ldaps(
        self, mock_get_ldaps, mock_get_spaces, mock_create_redis_client
    ):
        mock_get_spaces.return_value = {"spaceA": "Space A", "spaceB": "Space B"}
        mock_get_ldaps.return_value = {"user1": "User 1", "user2": "User 2"}

        mock_redis = Mock()
        mock_pipeline = Mock()
        # Pipeline returns results for all combinations:
        # 2 spaces × 2 users = 4 results
        mock_pipeline.execute.return_value = [10, 20, 30, 40]
        mock_redis.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-02",
            space_ids=None,
            sender_ldaps=None,
        )

        # Verify Microsoft LDAP function was called with ACTIVE status
        from src.common.constants import MicrosoftAccountStatus

        mock_get_ldaps.assert_called_once_with(MicrosoftAccountStatus.ACTIVE)

        # Verify all combinations are in result
        # Pipeline order: spaceA/user1, spaceA/user2, spaceB/user1, spaceB/user2
        self.assertEqual(result["user1"]["spaceA"], 10)
        self.assertEqual(result["user2"]["spaceA"], 20)
        self.assertEqual(result["user1"]["spaceB"], 30)
        self.assertEqual(result["user2"]["spaceB"], 40)

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    @patch("src.frontend_service.chat_query_utils.get_chat_spaces")
    @patch("src.frontend_service.chat_query_utils.get_all_ldaps_and_displaynames")
    def test_microsoft_ldap_fetch_error_raises(
        self, mock_get_ldaps, mock_get_spaces, mock_create_redis_client
    ):
        mock_get_spaces.return_value = {"spaceA": "Space A"}
        mock_get_ldaps.side_effect = Exception("Microsoft LDAP error")
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis

        with self.assertRaises(RuntimeError) as context:
            count_messages_in_date_range(
                start_date="2025-01-01",
                end_date="2025-01-02",
                space_ids=None,
                sender_ldaps=None,
            )
        self.assertIn(
            "Failed to fetch sender LDAPs from Microsoft directory",
            str(context.exception),
        )

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    @patch(
        "src.frontend_service.chat_query_utils.get_chat_spaces",
        side_effect=Exception("API error"),
    )
    def test_space_fetch_error(self, mock_get_spaces, mock_create_redis_client):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis

        with self.assertRaises(RuntimeError) as context:
            count_messages_in_date_range(
                start_date="2025-01-01",
                end_date="2025-01-02",
                space_ids=None,
                sender_ldaps=["user1"],
            )
        self.assertIn(
            "Failed to fetch space IDs from get_chat_spaces()", str(context.exception)
        )

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_redis_client_creation_failure(self, mock_create_redis_client):
        mock_create_redis_client.side_effect = Exception("Redis connection failed")

        with self.assertRaises(RuntimeError) as context:
            count_messages_in_date_range(
                start_date="2025-01-01",
                end_date="2025-01-31",
                space_ids=["space1"],
                sender_ldaps=["admin"],
            )
        self.assertIn("Failed to connect to Redis service", str(context.exception))

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_pipeline_execution_failure(self, mock_create_redis_client):
        """Test handling of Redis pipeline execution failure."""
        mock_redis_client = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = Exception("Pipeline execution failed")
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis_client

        with self.assertRaises(RuntimeError) as context:
            count_messages_in_date_range(
                start_date="2025-01-01",
                end_date="2025-01-31",
                space_ids=["space1"],
                sender_ldaps=["admin"],
            )
        self.assertIn(
            "Failed to execute Redis pipeline queries", str(context.exception)
        )

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_returns_correct_count_for_specific_space_user_combination(
        self, mock_create_redis_client
    ):
        """Test that the function correctly counts messages for specific space/user combinations."""
        mock_redis_client = Mock()
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = [5]
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-31",
            space_ids=["test_space"],
            sender_ldaps=["test_user"],
        )

        # Verify behavior result, not implementation details
        self.assertEqual(result["test_user"]["test_space"], 5)
        # Verify pipeline was used
        mock_pipeline.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
