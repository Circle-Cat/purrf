import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
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
        expected = UserContextDto("sub", "mail", "external", roles=[])
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
        expected = UserContextDto("sub", "mail", "external", roles=[])
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

    @patch("jwt.get_unverified_header")
    @patch("jwt.algorithms.RSAAlgorithm.from_jwk")
    @patch("backend.authentication.authentication_service.requests.get")
    def test_concurrent_cache_miss_only_fetches_jwks_once(
        self, mock_requests_get, mock_from_jwk, mock_get_header
    ):
        """
        N threads simultaneously hit a cache miss for the same kid.
        With double-checked locking + threading.Lock, only one network
        call should happen; the rest should pick up the populated cache
        after acquiring the lock.
        """
        kid = "shared_kid"
        n_threads = 10
        fake_key = "rsa_key_for_shared"
        mock_get_header.return_value = {"kid": kid}
        mock_from_jwk.return_value = fake_key

        # Slow the JWKS fetch so all threads queue at the lock before the
        # first one finishes — otherwise the test could pass for the wrong
        # reason (serial execution rather than locked execution).
        def slow_jwks_get(*_args, **_kwargs):
            time.sleep(0.05)
            resp = MagicMock()
            resp.json.return_value = {"keys": [{"kid": kid, "n": "x", "e": "y"}]}
            resp.raise_for_status = MagicMock()
            return resp

        mock_requests_get.side_effect = slow_jwks_get
        barrier = threading.Barrier(n_threads)

        def worker():
            barrier.wait()
            return self.auth_service._get_cf_signing_key("token-for-test")

        with ThreadPoolExecutor(max_workers=n_threads) as ex:
            results = [
                f.result() for f in [ex.submit(worker) for _ in range(n_threads)]
            ]

        self.assertEqual(mock_requests_get.call_count, 1)
        for r in results:
            self.assertEqual(r, fake_key)

    def test_build_context_cf_roles(self):
        """
        Test: Cloudflare role-building logic.
        """
        # Case 1: CC-internal upn user. identity_type defaults to "external"
        # for all Cloudflare users (internal/external policy deferred).
        payload = {
            "custom": {
                "upn": "dev@u.circlecat.org",
                "sub": "azure|abc",
                "hd": "circlecat.org",
                "iat": 1700000000,
                "extn.purrf_role": ["manager"],
            }
        }
        context = self.auth_service._build_context(payload, "cloudflare")
        self.assertIn(UserRole.CC_INTERNAL, context.roles)
        self.assertIn(UserRole.MANAGER, context.roles)
        self.assertIn(UserRole.MENTORSHIP, context.roles)
        # Raw Auth0 sub is used directly; no source prefix is added.
        self.assertEqual(context.sub, "azure|abc")
        self.assertEqual(context.primary_email, "dev@u.circlecat.org")
        self.assertEqual(context.identity_type, "external")
        self.assertEqual(context.last_login_at, 1700000000)

        # Case 2: External user (no hd claim) with Google Chat contact
        payload = {
            "custom": {
                "sub": "google-oauth2|123",
                "email": "hi@google.com",
                "iat": 1700000001,
            }
        }
        context = self.auth_service._build_context(payload, "cloudflare")
        self.assertIn(UserRole.CONTACT_GOOGLE_CHAT, context.roles)
        self.assertIn(UserRole.MENTORSHIP, context.roles)
        self.assertEqual(context.sub, "google-oauth2|123")
        self.assertEqual(context.identity_type, "external")
        self.assertEqual(context.last_login_at, 1700000001)

        # Case 3: Azure directory extension — roles stored as a JSON-encoded string because
        # Azure extension fields only support strings; Cloudflare wraps it in an outer array.
        payload = {
            "custom": {
                "upn": "dev@u.circlecat.org",
                "sub": "azure|abc",
                "extn.purrf_role": ['["mentorshipAdmin","manager"]'],
            }
        }
        context = self.auth_service._build_context(payload, "cloudflare")
        self.assertIn(UserRole.MANAGER, context.roles)
        self.assertIn(UserRole.MENTORSHIP_ADMIN, context.roles)

        # Case 4: custom.iat absent -> last_login_at is None
        payload = {"custom": {"sub": "email|xyz", "email": "user@example.com"}}
        context = self.auth_service._build_context(payload, "cloudflare")
        self.assertIsNone(context.last_login_at)
        self.assertEqual(context.identity_type, "external")
        self.assertEqual(context.sub, "email|xyz")

    def test_build_context_google_cron(self):
        """
        Test: Google cron / service account context-building.

        Ensures identity_type is "cronjob", last_login_at comes from the
        top-level payload iat, and the CRON_RUNNER role is assigned.
        """
        payload = {
            "email": "cron@test.com",
            "sub": "service-account|999",
            "iat": 1700000002,
        }
        context = self.auth_service._build_context(payload, "google")
        self.assertIn(UserRole.CRON_RUNNER, context.roles)
        self.assertEqual(context.sub, "service-account|999")
        self.assertEqual(context.primary_email, "cron@test.com")
        self.assertEqual(context.identity_type, "cronjob")
        self.assertEqual(context.last_login_at, 1700000002)


if __name__ == "__main__":
    unittest.main()
