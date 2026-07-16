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
