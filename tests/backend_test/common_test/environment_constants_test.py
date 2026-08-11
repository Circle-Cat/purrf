import importlib
import os
import unittest
from unittest.mock import patch

from backend.common import environment_constants


class TestGoogleServiceAccountSubs(unittest.TestCase):
    """
    Unit tests for parsing GOOGLE_SERVICE_ACCOUNT_SUBS.

    The value is read eagerly at import, so each case reloads the module under a
    patched environment and the class restores the real module afterwards.
    """

    @staticmethod
    def _reload_with(value):
        """
        Reload environment_constants with GOOGLE_SERVICE_ACCOUNT_SUBS set.

        Args:
            value (str | None): Raw environment value, or None to unset it.

        Returns:
            frozenset[str]: The parsed allowlist.
        """
        env = dict(os.environ)
        env.pop("GOOGLE_SERVICE_ACCOUNT_SUBS", None)
        if value is not None:
            env["GOOGLE_SERVICE_ACCOUNT_SUBS"] = value

        with patch.dict(os.environ, env, clear=True):
            importlib.reload(environment_constants)
            return environment_constants.GOOGLE_SERVICE_ACCOUNT_SUBS

    @classmethod
    def tearDownClass(cls):
        """Restore the module to what the real environment produces."""
        importlib.reload(environment_constants)

    def test_single_id(self):
        """The one-caller case, which is what Terraform injects today."""
        self.assertEqual(
            self._reload_with("111476081826269898524"),
            frozenset({"111476081826269898524"}),
        )

    def test_multiple_ids_are_split_on_commas(self):
        """A comma-separated value admits every id it lists."""
        self.assertEqual(self._reload_with("123,456"), frozenset({"123", "456"}))

    def test_surrounding_whitespace_is_stripped(self):
        """Without the strip, " 456" silently never matches a presented sub."""
        self.assertEqual(self._reload_with(" 123 , 456 "), frozenset({"123", "456"}))

    def test_trailing_comma_does_not_admit_an_empty_sub(self):
        """An empty entry would make the set non-empty and defeat the fail-closed check."""
        self.assertEqual(self._reload_with("123,"), frozenset({"123"}))

    def test_empty_value_yields_an_empty_allowlist(self):
        """An empty string parses to empty, which fails closed."""
        self.assertEqual(self._reload_with(""), frozenset())

    def test_unset_value_yields_an_empty_allowlist(self):
        """An unset variable parses to empty rather than raising."""
        self.assertEqual(self._reload_with(None), frozenset())


if __name__ == "__main__":
    unittest.main()
