import unittest

from backend.common.trusted_connections import is_trusted_email_assertion


class TestIsTrustedEmailAssertion(unittest.TestCase):
    def test_passwordless_verified_is_trusted(self):
        self.assertTrue(
            is_trusted_email_assertion("email|abc", True, "alice@example.com")
        )

    def test_google_oauth2_verified_is_trusted(self):
        self.assertTrue(
            is_trusted_email_assertion("google-oauth2|123", True, "alice@example.com")
        )

    def test_passwordless_unverified_is_not_trusted(self):
        self.assertFalse(
            is_trusted_email_assertion("email|abc", False, "alice@example.com")
        )

    def test_google_oauth2_unverified_is_not_trusted(self):
        self.assertFalse(
            is_trusted_email_assertion("google-oauth2|123", False, "alice@example.com")
        )

    def test_unlisted_connection_is_default_denied(self):
        """auth0 (database) and bare google prefixes are NOT allowlisted:
        an unlisted connection's assertion proves nothing regardless of
        email_verified."""
        self.assertFalse(is_trusted_email_assertion("auth0|123", True, "a@b.com"))
        self.assertFalse(is_trusted_email_assertion("google|123", True, "a@b.com"))

    def test_empty_or_prefixless_sub_is_denied(self):
        self.assertFalse(is_trusted_email_assertion("", True, "a@b.com"))
        self.assertFalse(is_trusted_email_assertion("emailabc", True, "a@b.com"))

    def test_google_oauth2_stale_verification_domain_is_denied(self):
        """u.circlecat.org is Microsoft-hosted mail (INTERNAL corp domain):
        Google's email_verified there is a stale, never-expiring historical
        claim, not live mailbox proof, so it must not be trusted."""
        self.assertFalse(
            is_trusted_email_assertion("google-oauth2|123", True, "x@u.circlecat.org")
        )

    def test_email_prefix_stale_verification_domain_is_still_trusted(self):
        """The stale-verification exclusion is google-oauth2-specific: a
        passwordless login is always a live OTP round-trip, regardless of
        domain."""
        self.assertTrue(
            is_trusted_email_assertion("email|abc", True, "x@u.circlecat.org")
        )

    def test_google_oauth2_stale_verification_domain_is_case_insensitive(self):
        """The domain comparison is case-insensitive."""
        self.assertFalse(
            is_trusted_email_assertion("google-oauth2|123", True, "x@U.CIRCLECAT.ORG")
        )


if __name__ == "__main__":
    unittest.main()
