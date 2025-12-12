import unittest
from unittest.mock import MagicMock, patch
from starlette.datastructures import Headers
from backend.authentication.authentication_service import (
    AuthenticationService,
    UserRole,
    UserContextDto,
)


class TestAuthenticationService(unittest.TestCase):
    """
    Unit tests for AuthenticationService.

    This suite verifies:
    - Cloudflare JWT verification (cache hit / cache miss)
    - Google ID token verification
    - Authentication routing between Cloudflare and Google
    - Role-building logic for various identity sources
    """

    def setUp(self):
        """
        Test initialization:

        1. Patch environment constants to avoid relying on actual environment values.
        2. Initialize an AuthenticationService instance with a mocked logger.
        """
        self.mock_logger = MagicMock()

        # Patch constant values used internally in the service
        self.patcher_constants = patch.multiple(
            "backend.authentication.authentication_service",
            CF_TEAM_DOMAIN="test.cloudflareaccess.com",
            CF_AUD_TAG="valid_cf_aud",
            GOOGLE_AUDIENCE="valid_google_aud",
            create=True,
        )
        self.patcher_constants.start()

        self.auth_service = AuthenticationService(self.mock_logger)

    def tearDown(self):
        """Stop all patched environment values."""
        self.patcher_constants.stop()

    @patch("jwt.decode")
    @patch("jwt.get_unverified_header")
    @patch(
        "backend.authentication.authentication_service.AuthenticationService._refresh_cf_keys"
    )
    def test_verify_cloudflare_cache_hit(
        self, mock_refresh, mock_get_header, mock_jwt_decode
    ):
        """
        Test: Cloudflare JWKS cache hit.

        Pre-populates the instance-level _CF_JWKS_CACHE and ensures:
        - Cached key is used
        - _refresh_cf_keys() is NOT called
        """
        token = "valid_cf_token"
        kid = "cached_kid_123"

        # Mock token header containing the cached kid
        mock_get_header.return_value = {"kid": kid}

        # Pre-populate instance cache
        mock_key = MagicMock()
        self.auth_service._CF_JWKS_CACHE[kid] = mock_key

        # Mock decode result
        mock_jwt_decode.return_value = {"custom": {"email": "test@test.com"}}

        self.auth_service._verify_cloudflare(token)

        mock_refresh.assert_not_called()
        mock_jwt_decode.assert_called_with(
            token,
            key=mock_key,
            audience="valid_cf_aud",
            algorithms=["RS256"],
            options={"verify_iss": True},
            issuer="https://test.cloudflareaccess.com",
        )

    @patch("jwt.decode")
    @patch("jwt.get_unverified_header")
    @patch("requests.get")
    @patch("jwt.algorithms.RSAAlgorithm.from_jwk")
    def test_verify_cloudflare_cache_miss_updates_instance_cache(
        self, mock_rsa, mock_requests_get, mock_get_header, mock_decode
    ):
        """
        Test: Cloudflare JWKS cache miss.

        Ensures:
        - A JWKS request is made
        - RSA key is constructed
        - The new key is stored in instance-level _CF_JWKS_CACHE
        """
        token = "token_new_key"
        kid = "new_kid_999"

        # Ensure cache starts empty
        self.assertEqual(self.auth_service._CF_JWKS_CACHE, {})

        # Mock header with new kid
        mock_get_header.return_value = {"kid": kid}

        # Mock JWKS response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [{"kid": kid, "n": "...", "e": "..."}]
        }
        mock_requests_get.return_value = mock_response

        # Mock RSA key conversion
        mock_rsa_key = "generated_rsa_key"
        mock_rsa.return_value = mock_rsa_key

        mock_decode.return_value = {"custom": {}}

        self.auth_service._verify_cloudflare(token)

        # Assert network request occurred
        mock_requests_get.assert_called_once()

        # Assert cache updated
        self.assertIn(kid, self.auth_service._CF_JWKS_CACHE)
        self.assertEqual(self.auth_service._CF_JWKS_CACHE[kid], mock_rsa_key)

    def test_auth_missing_credentials(self):
        """
        Test: authenticate_request should raise a ValueError
        when no authentication headers are provided.
        """
        headers = Headers({})
        with self.assertRaisesRegex(ValueError, "Missing authentication credentials"):
            self.auth_service.authenticate_request(headers)

    @patch(
        "backend.authentication.authentication_service.AuthenticationService._verify_cloudflare"
    )
    def test_auth_prefers_cloudflare(self, mock_verify_cf):
        """
        Test: When both Cloudflare and Google tokens exist,
        Cloudflare should always take priority.
        """
        headers = Headers({"Cf-Access-Jwt-Assertion": "cf_token"})
        expected = UserContextDto("sub", "mail", [])
        mock_verify_cf.return_value = expected

        result = self.auth_service.authenticate_request(headers)

        self.assertEqual(result, expected)
        mock_verify_cf.assert_called_with("cf_token")

    @patch(
        "backend.authentication.authentication_service.AuthenticationService._verify_google"
    )
    def test_auth_fallback_google(self, mock_verify_google):
        """
        Test: When Cloudflare token is absent, fallback to Google verification.
        """
        headers = Headers({"Authorization": "Bearer google_token"})
        expected = UserContextDto("sub", "mail", [])
        mock_verify_google.return_value = expected

        result = self.auth_service.authenticate_request(headers)

        self.assertEqual(result, expected)
        mock_verify_google.assert_called_with("google_token")

    @patch("google.oauth2.id_token.verify_token")
    def test_verify_google_valid(self, mock_verify):
        """
        Test: Valid Google ID token.

        Ensures:
        - Email and subject are extracted
        - CRON_RUNNER role is assigned when email matches
        - verify_token() is called with the proper client and audience
        """
        token = "g_token"
        mock_verify.return_value = {"email": "cron@test.com", "sub": "123"}

        context = self.auth_service._verify_google(token)

        self.assertEqual(context.primary_email, "cron@test.com")
        self.assertIn(UserRole.CRON_RUNNER, context.roles)
        mock_verify.assert_called_with(
            token, self.auth_service.google_request, audience="valid_google_aud"
        )

    def test_build_context_cf_roles(self):
        """
        Test: Cloudflare role-building logic.
        """
        # Case 1: Internal User
        payload = {
            "custom": {
                "upn": "dev@u.circlecat.org",
                "sub": "abc",
                "extn.purrf_role": ["admin"],
            }
        }
        context = self.auth_service._build_context(payload, "cloudflare")
        self.assertIn(UserRole.CC_INTERNAL, context.roles)
        self.assertIn(UserRole.ADMIN, context.roles)
        self.assertEqual(context.sub, "azure|abc")
        self.assertEqual(context.primary_email, "dev@u.circlecat.org")

        # Case 2: External user
        payload = {"custom": {"sub": "google-oauth2|123", "email": "hi@google.com"}}
        context = self.auth_service._build_context(payload, "cloudflare")
        self.assertIn(UserRole.CONTACT_GOOGLE_CHAT, context.roles)
        self.assertEqual(context.sub, "auth0|google-oauth2|123")


if __name__ == "__main__":
    unittest.main()
