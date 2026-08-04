import unittest

from backend.common.identity_type import IdentityType, is_rowless_login


class TestIsRowlessLogin(unittest.TestCase):
    def test_external_passwordless_is_rowless(self):
        self.assertTrue(is_rowless_login("email|abc", IdentityType.EXTERNAL))

    def test_external_passwordless_accepts_plain_string_type(self):
        # identity_type may arrive as the StrEnum's string value.
        self.assertTrue(is_rowless_login("email|abc", "external"))

    def test_internal_passwordless_is_rowless(self):
        # corp passwordless is now ALSO row-less; classification lives on
        # users.is_internal, not an identity row.
        self.assertTrue(is_rowless_login("email|abc", IdentityType.INTERNAL))

    def test_google_external_is_not_rowless(self):
        self.assertFalse(is_rowless_login("google-oauth2|abc", IdentityType.EXTERNAL))

    def test_google_internal_is_not_rowless(self):
        self.assertFalse(is_rowless_login("google-oauth2|abc", IdentityType.INTERNAL))


if __name__ == "__main__":
    unittest.main()
