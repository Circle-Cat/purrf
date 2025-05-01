import unittest
from unittest.mock import patch, Mock
from redis_dal.redis_query_utils import count_messages_in_date_range


class TestCountMessagesInDateRange(unittest.TestCase):
    @patch("redis_dal.redis_client_factory.RedisClientFactory.create_redis_client")
    def test_single_space_single_sender(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_redis_client.zcount.return_value = 3
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-31",
            space_ids=["space1"],
            sender_ldaps=["admin"],
        )
        self.assertEqual(result["admin"]["space1"], 3)

    @patch("redis_dal.redis_client_factory.RedisClientFactory.create_redis_client")
    def test_key_exists_but_zero_count(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_redis_client.zcount.return_value = 0
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-31",
            space_ids=["spaceX"],
            sender_ldaps=["admin"],
        )
        self.assertEqual(result["admin"]["spaceX"], 0)

    @patch("redis_dal.redis_client_factory.RedisClientFactory.create_redis_client")
    def test_key_does_not_exist(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_redis_client.zcount.return_value = 0
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-31",
            space_ids=["nonexistent_space"],
            sender_ldaps=["ghost"],
        )
        self.assertEqual(result["ghost"]["nonexistent_space"], 0)

    @patch("redis_dal.redis_client_factory.RedisClientFactory.create_redis_client")
    def test_multiple_spaces_and_senders(self, mock_create_redis_client):
        mock_redis_client = Mock()

        def fake_zcount(key, start, end):
            if key == "space1/admin":
                return 2
            elif key == "space2/bob":
                return 1
            return 0

        mock_redis_client.zcount.side_effect = fake_zcount
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

    def test_invalid_date_format(self):
        with self.assertRaises(ValueError):
            count_messages_in_date_range(
                start_date="invalid-date",
                end_date="2025-01-31",
                space_ids=["space1"],
                sender_ldaps=["admin"],
            )

    @patch("redis_dal.redis_client_factory.RedisClientFactory.create_redis_client")
    def test_default_dates(self, mock_create_redis_client):
        mock_redis_client = Mock()
        mock_redis_client.zcount.return_value = 5
        mock_create_redis_client.return_value = mock_redis_client

        result = count_messages_in_date_range(
            start_date=None, end_date=None, space_ids=["space1"], sender_ldaps=["admin"]
        )
        self.assertIn("admin", result)
        self.assertEqual(result["admin"]["space1"], 5)

    @patch("redis_dal.redis_client_factory.RedisClientFactory.create_redis_client")
    @patch("redis_dal.redis_query_utils.get_chat_spaces")
    @patch("redis_dal.redis_query_utils.list_directory_all_people_ldap")
    def test_fallback_to_all_spaces_and_senders(
        self, mock_list_ldap, mock_get_spaces, mock_create_redis_client
    ):
        mock_get_spaces.return_value = {"spaceA": "Space A", "spaceB": "Space B"}
        mock_list_ldap.return_value = {"u1": "user1", "u2": "user2"}

        mock_redis = Mock()
        mock_redis.zcount.return_value = 10
        mock_create_redis_client.return_value = mock_redis

        result = count_messages_in_date_range(
            start_date="2025-01-01",
            end_date="2025-01-02",
            space_ids=None,
            sender_ldaps=None,
        )

        self.assertEqual(result["user1"]["spaceA"], 10)
        self.assertEqual(result["user2"]["spaceB"], 10)

    @patch("redis_dal.redis_client_factory.RedisClientFactory.create_redis_client")
    @patch(
        "redis_dal.redis_query_utils.get_chat_spaces",
        side_effect=Exception("API error"),
    )
    @patch(
        "redis_dal.redis_query_utils.list_directory_all_people_ldap",
        side_effect=Exception("LDAP error"),
    )
    def test_fallback_fetch_error(
        self, mock_list_ldap, mock_get_spaces, mock_create_redis_client
    ):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis

        with self.assertRaises(RuntimeError) as context:
            count_messages_in_date_range(
                start_date="2025-01-01",
                end_date="2025-01-02",
                space_ids=None,
                sender_ldaps=None,
            )
        self.assertIsNotNone(context.exception.__cause__)
        self.assertIn("API error", str(context.exception.__cause__))


if __name__ == "__main__":
    unittest.main()
