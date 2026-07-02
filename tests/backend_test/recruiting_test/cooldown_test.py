import unittest
from datetime import date
from backend.common.recruiting_enums import JobKind
from backend.recruiting.cooldown import compute_thaw, is_in_cooldown


class TestCooldown(unittest.TestCase):
    def test_mentorship_prd_example_jan_reject_thaws_april_1(self):
        # Apply Jan 2026 for round 1 (starts Feb), rejected -> thaw 2026-04-01
        thaw = compute_thaw(
            JobKind.ACTIVITY, date(2026, 1, 10), date(2026, 1, 20), None
        )
        self.assertEqual(thaw, date(2026, 4, 1))

    def test_mentorship_applied_for_round2_thaws_before_round3(self):
        # Apply during off window before May round -> target May(R2), next Sep(R3)
        thaw = compute_thaw(JobKind.ACTIVITY, date(2026, 4, 15), date(2026, 5, 2), None)
        self.assertEqual(thaw, date(2026, 8, 1))

    def test_mentorship_round3_wraps_to_next_year_round1(self):
        # Target Sep(R3), next Feb(R1) next year -> thaw Jan 1 next year
        thaw = compute_thaw(JobKind.ACTIVITY, date(2026, 9, 5), date(2026, 9, 20), None)
        self.assertEqual(thaw, date(2027, 1, 1))

    def test_employment_uses_fixed_cooldown_days(self):
        thaw = compute_thaw(JobKind.EMPLOYMENT, date(2026, 1, 1), date(2026, 3, 1), 90)
        self.assertEqual(thaw, date(2026, 5, 30))

    def test_employment_missing_cooldown_days_is_zero(self):
        thaw = compute_thaw(
            JobKind.EMPLOYMENT, date(2026, 1, 1), date(2026, 3, 1), None
        )
        self.assertEqual(thaw, date(2026, 3, 1))

    def test_is_in_cooldown(self):
        self.assertTrue(is_in_cooldown(date(2026, 3, 31), date(2026, 4, 1)))
        self.assertFalse(is_in_cooldown(date(2026, 4, 1), date(2026, 4, 1)))


if __name__ == "__main__":
    unittest.main()
