from unittest import TestCase, main
from unittest.mock import patch, Mock, call
from src.frontend_service.ldap_loader import get_all_ldaps_and_displaynames
from src.common.constants import (
    MicrosoftAccountStatus,
    MICROSOFT_LDAP_KEY,
)


class TestLdapLoader(TestCase):
    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_active_status_returns_active_dict(self, mock_create_redis_client):
        mock_redis = Mock()
        active_data = {"ldap1": "displayname1", "ldap2": "displayname2"}
        mock_redis.hgetall.return_value = active_data
        mock_create_redis_client.return_value = mock_redis

        result = get_all_ldaps_and_displaynames(MicrosoftAccountStatus.ACTIVE)
        mock_redis.hgetall.assert_called_once_with(
            MICROSOFT_LDAP_KEY.format(
                account_status=MicrosoftAccountStatus.ACTIVE.value
            )
        )
        self.assertEqual(result, active_data)

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_terminated_status_returns_terminated_dict(self, mock_create_redis_client):
        mock_redis = Mock()
        terminated_data = {"ldap3": "displayname3"}
        mock_redis.hgetall.return_value = terminated_data
        mock_create_redis_client.return_value = mock_redis

        result = get_all_ldaps_and_displaynames(MicrosoftAccountStatus.TERMINATED)
        mock_redis.hgetall.assert_called_once_with(
            MICROSOFT_LDAP_KEY.format(
                account_status=MicrosoftAccountStatus.TERMINATED.value
            )
        )
        self.assertEqual(result, terminated_data)

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_all_status_returns_merged_dict(self, mock_create_redis_client):
        mock_redis = Mock()
        active_data = {"ldap1": "displayname1"}
        terminated_data = {"ldap3": "displayname3"}

        mock_redis.hgetall.side_effect = [active_data, terminated_data]
        mock_create_redis_client.return_value = mock_redis

        result = get_all_ldaps_and_displaynames(MicrosoftAccountStatus.ALL)

        calls = [
            call(
                MICROSOFT_LDAP_KEY.format(
                    account_status=MicrosoftAccountStatus.ACTIVE.value
                )
            ),
            call(
                MICROSOFT_LDAP_KEY.format(
                    account_status=MicrosoftAccountStatus.TERMINATED.value
                )
            ),
        ]
        mock_redis.hgetall.assert_has_calls(calls)
        expected = active_data.copy()
        expected.update(terminated_data)
        self.assertEqual(result, expected)

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_redis_client_not_created_raises(self, mock_create_redis_client):
        mock_create_redis_client.return_value = None
        with self.assertRaises(ValueError):
            get_all_ldaps_and_displaynames(MicrosoftAccountStatus.ACTIVE)
        self.assertEqual(mock_create_redis_client.call_count, 3)

    @patch("src.common.redis_client.RedisClientFactory.create_redis_client")
    def test_unsupported_status_raises(self, mock_create_redis_client):
        mock_redis = Mock()
        mock_create_redis_client.return_value = mock_redis
        with self.assertRaises(ValueError):
            get_all_ldaps_and_displaynames("unsupported_status")
        self.assertEqual(mock_create_redis_client.call_count, 3)
        mock_redis.hgetall.assert_not_called()


if __name__ == "__main__":
    main()
