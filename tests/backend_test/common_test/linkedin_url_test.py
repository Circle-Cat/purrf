import unittest

from backend.common.linkedin_url import normalize_linkedin_profile_url


class TestNormalizeLinkedinProfileUrl(unittest.TestCase):
    def test_keeps_an_https_linkedin_link(self):
        self.assertEqual(
            normalize_linkedin_profile_url("https://www.linkedin.com/in/ann"),
            "https://www.linkedin.com/in/ann",
        )

    def test_accepts_the_bare_domain_and_http(self):
        self.assertEqual(
            normalize_linkedin_profile_url("http://linkedin.com/in/ann"),
            "http://linkedin.com/in/ann",
        )

    def test_adds_https_to_a_link_without_scheme(self):
        self.assertEqual(
            normalize_linkedin_profile_url("  www.linkedin.com/in/ann "),
            "https://www.linkedin.com/in/ann",
        )

    def test_rejects_script_and_data_urls_mentioning_linkedin(self):
        for url in (
            "javascript:alert(1)//linkedin.com",
            "JavaScript:alert(1)//www.linkedin.com/in/ann",
            "data:text/html,linkedin.com",
        ):
            with self.subTest(url=url):
                self.assertIsNone(normalize_linkedin_profile_url(url))

    def test_rejects_other_hosts(self):
        for url in (
            "https://github.com/ann",
            "https://linkedin.com.evil.example/in/ann",
            "https://evil.example/linkedin.com/in/ann",
            "https://notlinkedin.com/in/ann",
        ):
            with self.subTest(url=url):
                self.assertIsNone(normalize_linkedin_profile_url(url))

    def test_rejects_empty_input(self):
        for url in (None, "", "   "):
            with self.subTest(url=url):
                self.assertIsNone(normalize_linkedin_profile_url(url))


if __name__ == "__main__":
    unittest.main()
