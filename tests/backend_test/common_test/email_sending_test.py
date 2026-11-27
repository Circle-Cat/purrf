"""The switch that stops an environment sending email."""

import os
import unittest
from unittest.mock import patch

from backend.common.email_sending import (
    EmailSendingDisabledError,
    email_sending_enabled,
)


class TestEmailSendingEnabled(unittest.TestCase):
    def _enabled(self, value):
        with patch.dict(os.environ, {"EMAIL_SENDING_ENABLED": value}):
            return email_sending_enabled()

    def test_unset_means_on(self):
        """Prod leaves it unset; a missing variable must never silence prod."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(email_sending_enabled())

    def test_false_in_any_spelling_switches_it_off(self):
        for value in ("false", "FALSE", " False ", "0", "no", "off"):
            with self.subTest(value=value):
                self.assertFalse(self._enabled(value))

    def test_anything_else_leaves_it_on(self):
        for value in ("true", "1", "yes", "", "anything"):
            with self.subTest(value=value):
                self.assertTrue(self._enabled(value))


class TestEmailSendingDisabledError(unittest.TestCase):
    def test_reads_as_a_bad_request_and_as_a_permanent_delivery_failure(self):
        """ValueError answers 400 to a person who started the send; LookupError
        is what notification delivery treats as never retryable."""
        error = EmailSendingDisabledError("x")
        self.assertIsInstance(error, ValueError)
        self.assertIsInstance(error, LookupError)


if __name__ == "__main__":
    unittest.main()
