import unittest
from datetime import date
from backend.recruiting.cooldown import compute_thaw, is_in_cooldown


class TestCooldown(unittest.TestCase):
    def test_uses_fixed_cooldown_days(self):
        thaw = compute_thaw(date(2026, 3, 1), 90)
        self.assertEqual(thaw, date(2026, 5, 30))

    def test_missing_cooldown_days_is_zero(self):
        thaw = compute_thaw(date(2026, 3, 1), None)
        self.assertEqual(thaw, date(2026, 3, 1))

    def test_zero_cooldown_days_is_immediate(self):
        thaw = compute_thaw(date(2026, 1, 20), 0)
        self.assertEqual(thaw, date(2026, 1, 20))

    def test_is_in_cooldown(self):
        self.assertTrue(is_in_cooldown(date(2026, 3, 31), date(2026, 4, 1)))
        self.assertFalse(is_in_cooldown(date(2026, 4, 1), date(2026, 4, 1)))


if __name__ == "__main__":
    unittest.main()
