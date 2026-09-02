"""Refusing to start when course files would be served from an app origin."""

import unittest

from backend.training.content_host import assert_content_host_isolated, hostname_of

_APP_ORIGINS = "https://purrf.io,https://api.purrf.io"


class TestHostnameOf(unittest.TestCase):
    def test_an_origin_and_a_bare_hostname_read_the_same(self):
        self.assertEqual(hostname_of("https://purrf.io"), "purrf.io")
        self.assertEqual(hostname_of("purrf.io"), "purrf.io")

    def test_a_port_and_a_path_are_not_part_of_the_hostname(self):
        self.assertEqual(hostname_of("https://purrf.io:8443/app"), "purrf.io")

    def test_an_empty_entry_has_no_hostname(self):
        self.assertEqual(hostname_of("   "), "")


class TestAssertContentHostIsolated(unittest.TestCase):
    def test_a_separate_content_host_is_accepted(self):
        assert_content_host_isolated("training-content.purrf.io", _APP_ORIGINS)

    def test_content_hosting_that_is_not_configured_is_not_checked(self):
        """No content host means the route and the middleware exemption both
        already refuse everything, so there is nothing to compare."""
        assert_content_host_isolated(None, None)
        assert_content_host_isolated("", None)

    def test_serving_content_from_the_api_origin_refuses_to_start(self):
        with self.assertRaises(ValueError) as caught:
            assert_content_host_isolated("api.purrf.io", _APP_ORIGINS)

        self.assertIn("api.purrf.io", str(caught.exception))

    def test_serving_content_from_the_web_origin_refuses_to_start(self):
        with self.assertRaises(ValueError):
            assert_content_host_isolated("purrf.io", _APP_ORIGINS)

    def test_a_content_host_written_as_a_url_refuses_to_start(self):
        """It is compared against the Host header exactly, so a value with a
        scheme matches nothing and every asset 404s with no other signal."""
        with self.assertRaises(ValueError):
            assert_content_host_isolated("https://training.purrf.io", _APP_ORIGINS)

    def test_a_content_host_carrying_a_port_refuses_to_start(self):
        with self.assertRaises(ValueError):
            assert_content_host_isolated("training.purrf.io:443", _APP_ORIGINS)

    def test_a_content_host_that_is_not_lowercase_refuses_to_start(self):
        with self.assertRaises(ValueError):
            assert_content_host_isolated("Training.Purrf.io", _APP_ORIGINS)

    def test_unknown_app_origins_refuse_to_start(self):
        """Without them the check cannot be made at all, and an unchecked
        content host is the thing this exists to prevent."""
        for origins in (None, "", "  ,  "):
            with self.subTest(origins=origins):
                with self.assertRaises(ValueError) as caught:
                    assert_content_host_isolated("training.purrf.io", origins)

                self.assertIn("APP_ORIGINS", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
