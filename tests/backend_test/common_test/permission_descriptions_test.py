import unittest

from backend.common.permission_descriptions import (
    PERMISSION_DESCRIPTIONS,
    _validate_complete,
)
from backend.common.permissions import Permission


class TestPermissionDescriptions(unittest.TestCase):
    def test_covers_every_enum_member(self):
        self.assertEqual(set(PERMISSION_DESCRIPTIONS), set(Permission))

    def test_every_description_is_a_non_empty_string(self):
        for permission, description in PERMISSION_DESCRIPTIONS.items():
            self.assertIsInstance(description, str)
            self.assertTrue(description.strip())

    def test_validate_complete_returns_dict_when_full(self):
        full = {p: "x" for p in Permission}
        self.assertEqual(_validate_complete(full), full)

    def test_validate_complete_raises_on_missing_entry(self):
        incomplete = {
            p: "x" for p in Permission if p != Permission.SUPER_ADMIN_REVOKE
        }
        with self.assertRaises(ValueError):
            _validate_complete(incomplete)


if __name__ == "__main__":
    unittest.main()
