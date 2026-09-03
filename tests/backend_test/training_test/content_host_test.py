"""Deciding whether course files may be served, and disabling them if not."""

import unittest
from unittest.mock import MagicMock

from backend.training.content_host import hostname_of, resolve_content_host

_APP_ORIGINS = "https://purrf.io,https://api.purrf.io"
_CONTENT_HOST = "training-content.purrf.io"


class TestHostnameOf(unittest.TestCase):
    def test_an_origin_and_a_bare_hostname_read_the_same(self):
        self.assertEqual(hostname_of("https://purrf.io"), "purrf.io")
        self.assertEqual(hostname_of("purrf.io"), "purrf.io")

    def test_a_port_and_a_path_are_not_part_of_the_hostname(self):
        self.assertEqual(hostname_of("https://purrf.io:8443/app"), "purrf.io")

    def test_an_empty_entry_has_no_hostname(self):
        self.assertEqual(hostname_of("   "), "")


class _ResolveCase(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()

    def resolve(self, content_host, app_origins):
        return resolve_content_host(content_host, app_origins, self.logger)

    def logged_error(self):
        self.assertTrue(self.logger.error.called, msg="nothing was logged")
        template, *arguments = self.logger.error.call_args.args
        return template % tuple(arguments)


class TestContentHostingStaysOn(_ResolveCase):
    def test_a_separate_content_host_is_served(self):
        self.assertEqual(self.resolve(_CONTENT_HOST, _APP_ORIGINS), _CONTENT_HOST)
        self.logger.error.assert_not_called()

    def test_app_origins_written_as_bare_hostnames_still_compare(self):
        self.assertEqual(
            self.resolve(_CONTENT_HOST, "purrf.io, api.purrf.io"), _CONTENT_HOST
        )
        self.logger.error.assert_not_called()

    def test_content_hosting_that_is_nobody_configured_is_silent(self):
        """No content host is a normal environment, not a misconfiguration."""
        for value in (None, ""):
            with self.subTest(value=value):
                self.assertIsNone(self.resolve(value, None))

        self.logger.error.assert_not_called()


class TestContentHostingIsDisabled(_ResolveCase):
    """Never an exception: one optional feature that cannot verify its own
    wiring must not stop login, mentorship and recruiting from starting."""

    def test_a_content_host_that_is_an_app_origin_is_refused(self):
        self.assertIsNone(self.resolve("api.purrf.io", _APP_ORIGINS))
        self.assertIn("api.purrf.io", self.logged_error())

    def test_a_content_host_that_is_the_web_origin_is_refused(self):
        self.assertIsNone(self.resolve("purrf.io", _APP_ORIGINS))

    def test_unknown_app_origins_disable_content_rather_than_trust_it(self):
        for origins in (None, "", "  ,  "):
            with self.subTest(origins=origins):
                self.logger.reset_mock()

                self.assertIsNone(self.resolve(_CONTENT_HOST, origins))

                self.assertIn("APP_ORIGINS", self.logged_error())

    def test_the_log_says_what_to_set(self):
        self.resolve(_CONTENT_HOST, None)

        logged = self.logged_error()
        self.assertIn("APP_ORIGINS", logged)
        self.assertIn("https://purrf.io", logged)

    def test_a_content_host_written_as_a_url_is_refused(self):
        """It is compared against the Host header exactly, so a value with a
        scheme matches nothing and every asset 404s with no other signal."""
        self.assertIsNone(self.resolve("https://training.purrf.io", _APP_ORIGINS))
        self.assertIn("hostname", self.logged_error())

    def test_a_content_host_carrying_a_port_is_refused(self):
        self.assertIsNone(self.resolve("training.purrf.io:443", _APP_ORIGINS))

    def test_a_content_host_that_is_not_lowercase_is_refused(self):
        self.assertIsNone(self.resolve("Training.Purrf.io", _APP_ORIGINS))


if __name__ == "__main__":
    unittest.main()
