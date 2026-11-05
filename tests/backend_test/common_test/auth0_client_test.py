import time
import unittest
from unittest.mock import MagicMock, patch

import jwt

from backend.common.auth0_client import Auth0Client
from backend.common.exceptions import RateLimitedError


def _response(status_code: int, body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = body if body is not None else {}
    resp.text = str(body)
    return resp


class TestAuth0Client(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        # Constructor reads env (all None here) and builds a PyJWKClient without
        # any network call, so it is safe to instantiate directly.
        self.client = Auth0Client(self.logger)

    @patch("backend.common.auth0_client.requests")
    def test_start_passwordless_success(self, mock_requests):
        mock_requests.post.return_value = _response(200, {})
        self.client.start_passwordless("alice@gmail.com")
        mock_requests.post.assert_called_once()

    @patch("backend.common.auth0_client.requests")
    def test_start_passwordless_rate_limited(self, mock_requests):
        mock_requests.post.return_value = _response(429, {"error": "too_many_requests"})
        with self.assertRaises(RateLimitedError):
            self.client.start_passwordless("alice@gmail.com")

    @patch("backend.common.auth0_client.requests")
    def test_start_passwordless_server_error(self, mock_requests):
        mock_requests.post.return_value = _response(500, {"error": "server_error"})
        with self.assertRaises(RuntimeError):
            self.client.start_passwordless("alice@gmail.com")

    @patch("backend.common.auth0_client.requests")
    def test_exchange_otp_success_returns_verified_claims(self, mock_requests):
        mock_requests.post.return_value = _response(200, {"id_token": "signed.jwt"})
        claims = {
            "sub": "email|abc",
            "email": "alice@gmail.com",
            "email_verified": True,
        }
        with patch.object(
            self.client, "_verify_id_token", return_value=claims
        ) as verify:
            result = self.client.exchange_otp("alice@gmail.com", "123456")
        verify.assert_called_once_with("signed.jwt")
        self.assertEqual(result, claims)

    @patch("backend.common.auth0_client.requests")
    def test_exchange_otp_wrong_code_is_value_error(self, mock_requests):
        mock_requests.post.return_value = _response(
            403,
            {
                "error": "invalid_grant",
                "error_description": "Wrong email or verification code.",
            },
        )
        with self.assertRaises(ValueError):
            self.client.exchange_otp("alice@gmail.com", "000000")

    @patch("backend.common.auth0_client.requests")
    def test_exchange_otp_rate_limited(self, mock_requests):
        mock_requests.post.return_value = _response(429, {"error": "too_many_requests"})
        with self.assertRaises(RateLimitedError):
            self.client.exchange_otp("alice@gmail.com", "123456")

    @patch("backend.common.auth0_client.requests")
    def test_exchange_otp_other_error_is_runtime_error(self, mock_requests):
        mock_requests.post.return_value = _response(500, {"error": "server_error"})
        with self.assertRaises(RuntimeError):
            self.client.exchange_otp("alice@gmail.com", "123456")

    @patch("backend.common.auth0_client.requests")
    def test_delete_user_success(self, mock_requests):
        mock_requests.delete.return_value = _response(204)
        with patch.object(self.client, "_get_m2m_token", return_value="m2m-token"):
            self.client.delete_user("email|abc123")
        _, kwargs = mock_requests.delete.call_args
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer m2m-token",
        )

    @patch("backend.common.auth0_client.requests")
    def test_delete_user_encodes_sub_in_url(self, mock_requests):
        mock_requests.delete.return_value = _response(204)
        with patch.object(self.client, "_get_m2m_token", return_value="m2m-token"):
            self.client.delete_user("google-oauth2|12345")
        url = mock_requests.delete.call_args[0][0]
        self.assertIn("/api/v2/users/google-oauth2%7C12345", url)

    @patch("backend.common.auth0_client.requests")
    def test_delete_user_404_is_idempotent_success(self, mock_requests):
        mock_requests.delete.return_value = _response(404, {"error": "inexistent_user"})
        with patch.object(self.client, "_get_m2m_token", return_value="m2m-token"):
            self.client.delete_user("email|gone")

    @patch("backend.common.auth0_client.requests")
    def test_delete_user_rate_limited(self, mock_requests):
        mock_requests.delete.return_value = _response(429, {"error": "too_many"})
        with patch.object(self.client, "_get_m2m_token", return_value="m2m-token"):
            with self.assertRaises(RateLimitedError):
                self.client.delete_user("email|abc123")

    @patch("backend.common.auth0_client.requests")
    def test_delete_user_server_error_is_runtime_error(self, mock_requests):
        mock_requests.delete.return_value = _response(500, {"error": "server_error"})
        with patch.object(self.client, "_get_m2m_token", return_value="m2m-token"):
            with self.assertRaises(RuntimeError):
                self.client.delete_user("email|abc123")

    @patch("backend.common.auth0_client.requests")
    def test_get_m2m_token_fetches_then_reuses_cache(self, mock_requests):
        mock_requests.post.return_value = _response(
            200, {"access_token": "m2m-token", "expires_in": 3600}
        )
        first = self.client._get_m2m_token()
        second = self.client._get_m2m_token()
        self.assertEqual(first, "m2m-token")
        self.assertEqual(second, "m2m-token")
        mock_requests.post.assert_called_once()

    @patch("backend.common.auth0_client.requests")
    def test_get_m2m_token_refreshes_near_expiry(self, mock_requests):
        mock_requests.post.return_value = _response(
            200, {"access_token": "fresh-token", "expires_in": 3600}
        )
        # A cached token inside the refresh buffer must not be reused.
        self.client._m2m_token_cache = {
            "access_token": "stale-token",
            "expires_at": time.time() + 10,
        }
        self.assertEqual(self.client._get_m2m_token(), "fresh-token")
        mock_requests.post.assert_called_once()

    @patch("backend.common.auth0_client.requests")
    def test_get_m2m_token_error_is_runtime_error(self, mock_requests):
        mock_requests.post.return_value = _response(401, {"error": "access_denied"})
        with self.assertRaises(RuntimeError):
            self.client._get_m2m_token()

    def test_verify_id_token_bad_signature_is_value_error(self):
        self.client._jwks_client = MagicMock()
        with patch(
            "backend.common.auth0_client.jwt.decode",
            side_effect=jwt.InvalidSignatureError("bad"),
        ):
            with self.assertRaises(ValueError):
                self.client._verify_id_token("tampered.jwt")


if __name__ == "__main__":
    unittest.main()
