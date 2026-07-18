import unittest

from backend.common.trusted_connections import is_trusted_email_assertion


class TestIsTrustedEmailAssertion(unittest.TestCase):
    def test_passwordless_verified_is_trusted(self):
        self.assertTrue(is_trusted_email_assertion("email|abc", True))

    def test_google_oauth2_verified_is_trusted(self):
        self.assertTrue(is_trusted_email_assertion("google-oauth2|123", True))

    def test_passwordless_unverified_is_not_trusted(self):
        self.assertFalse(is_trusted_email_assertion("email|abc", False))

    def test_google_oauth2_unverified_is_not_trusted(self):
        self.assertFalse(is_trusted_email_assertion("google-oauth2|123", False))

    def test_unlisted_connection_is_default_denied(self):
        """auth0 (database) and bare google prefixes are NOT allowlisted:
        an unlisted connection's assertion proves nothing regardless of
        email_verified."""
        self.assertFalse(is_trusted_email_assertion("auth0|123", True))
        self.assertFalse(is_trusted_email_assertion("google|123", True))

    def test_empty_or_prefixless_sub_is_denied(self):
        self.assertFalse(is_trusted_email_assertion("", True))
        self.assertFalse(is_trusted_email_assertion("emailabc", True))


if __name__ == "__main__":
    unittest.main()
