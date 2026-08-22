import unittest

from backend.leave.employment_profile import (
    EmploymentProfile,
    ProfileProblem,
    build_employment_profile,
    is_in_leave_scope,
)


class BuildEmploymentProfileTest(unittest.TestCase):
    """A raw Graph user payload becomes an EmploymentProfile or a named problem."""

    def _raw(self, **overrides) -> dict:
        raw = {
            "mail": "alice@u.circlecat.org",
            "employeeType": "Full-time Employee",
            "officeLocation": "CN-CAN-ZQ",
            "jobTitle": "Software Engineer (L3)",
            "employeeHireDate": "2024-03-01T00:00:00Z",
            "employeeLeaveDateTime": None,
            "managerLdap": "bob",
        }
        raw.update(overrides)
        return raw

    def test_full_time_cn_swe_is_eligible_with_parsed_level(self):
        profile = build_employment_profile(self._raw())

        self.assertEqual(
            profile,
            EmploymentProfile(
                ldap="alice",
                level="L3",
                annual_hours=80,
                hire_date="2024-03-01",
                leave_date=None,
                manager_ldap="bob",
                problems=(),
            ),
        )

    def test_non_swe_job_title_gets_zero_hours_and_no_problem(self):
        """Deliberately silent: entitlement is 0h and admins are not alerted."""
        profile = build_employment_profile(self._raw(jobTitle="Office Manager"))

        self.assertEqual(profile.annual_hours, 0)
        self.assertIsNone(profile.level)
        self.assertEqual(profile.problems, ())

    def test_missing_hire_date_is_reported_as_a_problem(self):
        profile = build_employment_profile(self._raw(employeeHireDate=None))

        self.assertEqual(profile.problems, (ProfileProblem.MISSING_HIRE_DATE,))

    def test_missing_manager_is_reported_as_a_problem(self):
        profile = build_employment_profile(self._raw(managerLdap=None))

        self.assertEqual(profile.problems, (ProfileProblem.MISSING_MANAGER,))

    def test_unparseable_job_title_shaped_like_a_level_is_a_problem(self):
        """`Software Engineer (L9)` is a typo, not a non-SWE role."""
        profile = build_employment_profile(self._raw(jobTitle="Software Engineer (L9)"))

        self.assertEqual(profile.problems, (ProfileProblem.UNPARSEABLE_JOB_TITLE,))

    def test_level_parsing_ignores_case(self):
        profile = build_employment_profile(self._raw(jobTitle="software engineer (l2)"))

        self.assertEqual(profile.level, "L2")
        self.assertEqual(profile.annual_hours, 80)

    def test_hire_date_is_the_beijing_calendar_date_not_the_utc_one(self):
        """Azure stores Beijing midnight as 16:00 the previous day in UTC.

        Truncating the timestamp gives the UTC date, which is a day early. The
        hire date is the accrual start point, so that day is real.
        """
        profile = build_employment_profile(
            self._raw(employeeHireDate="2025-03-23T16:00:00+00:00")
        )

        self.assertEqual(profile.hire_date, "2025-03-24")

    def test_a_date_already_carrying_the_beijing_offset_is_unchanged(self):
        """The conversion is a no-op when Azure already hands back +08:00."""
        profile = build_employment_profile(
            self._raw(employeeHireDate="2024-03-01T00:00:00+08:00")
        )

        self.assertEqual(profile.hire_date, "2024-03-01")

    def test_a_date_already_on_the_beijing_day_is_unchanged(self):
        profile = build_employment_profile(
            self._raw(employeeHireDate="2024-03-01T00:00:00Z")
        )

        self.assertEqual(profile.hire_date, "2024-03-01")

    def test_leave_date_gets_the_same_treatment(self):
        profile = build_employment_profile(
            self._raw(employeeLeaveDateTime="2025-06-30T16:00:00+00:00")
        )

        self.assertEqual(profile.leave_date, "2025-07-01")

    def test_l1_is_eligible_but_has_no_entitlement(self):
        profile = build_employment_profile(self._raw(jobTitle="Software Engineer (L1)"))

        self.assertEqual(profile.level, "L1")
        self.assertEqual(profile.annual_hours, 0)
        self.assertEqual(profile.problems, ())


class IsInLeaveScopeTest(unittest.TestCase):
    """Who the leave system covers, judged on the two Azure fields it can see.

    ``users.is_internal`` is the third condition and is checked by the caller,
    which has the purrf row; this function only sees the Graph payload.
    """

    def _raw(self, **overrides) -> dict:
        raw = {
            "employeeType": "Full-time Employee",
            "officeLocation": "CN-CAN-ZQ",
        }
        raw.update(overrides)
        return raw

    def test_full_time_china_employee_is_in_scope(self):
        self.assertTrue(is_in_leave_scope(self._raw()))

    def test_intern_is_out_of_scope(self):
        self.assertFalse(is_in_leave_scope(self._raw(employeeType="Intern")))

    def test_non_china_office_is_out_of_scope(self):
        self.assertFalse(is_in_leave_scope(self._raw(officeLocation="US-CA-SFO")))

    def test_missing_employee_type_is_out_of_scope(self):
        self.assertFalse(is_in_leave_scope(self._raw(employeeType=None)))

    def test_missing_office_location_is_out_of_scope(self):
        self.assertFalse(is_in_leave_scope(self._raw(officeLocation=None)))

    def test_china_prefix_match_is_anchored_at_the_start(self):
        """`ACN-` must not pass by containing `CN-`."""
        self.assertFalse(is_in_leave_scope(self._raw(officeLocation="ACN-XYZ")))

    def test_bare_cn_without_a_separator_is_out_of_scope(self):
        """The documented shape is `CN-CAN-ZQ`; a bare `CN` is not it."""
        self.assertFalse(is_in_leave_scope(self._raw(officeLocation="CN")))


class TestAccountEnabled(unittest.TestCase):
    """The accrual engine's fallback for "has left".

    A leaver is supposed to carry employeeLeaveDateTime, and one of the five
    China full-timers in the directory is disabled with that field empty. On
    the leave date alone that person would keep accruing for good.
    """

    def test_a_disabled_account_is_carried_onto_the_profile(self):
        profile = build_employment_profile({
            "mail": "ann@circlecat.org",
            "jobTitle": "Software Engineer (L3)",
            "employeeHireDate": "2024-03-01T00:00:00Z",
            "managerLdap": "bob",
            "accountEnabled": False,
        })

        self.assertFalse(profile.account_enabled)

    def test_an_enabled_account_is_carried_onto_the_profile(self):
        profile = build_employment_profile({
            "mail": "ann@circlecat.org",
            "jobTitle": "Software Engineer (L3)",
            "employeeHireDate": "2024-03-01T00:00:00Z",
            "managerLdap": "bob",
            "accountEnabled": True,
        })

        self.assertTrue(profile.account_enabled)

    def test_a_payload_without_the_field_counts_as_enabled(self):
        """Erring the other way would stop accrual for the entire directory
        the moment the field went missing, and stopping is invisible in a
        balance while over-paying is not."""
        profile = build_employment_profile({
            "mail": "ann@circlecat.org",
            "jobTitle": "Software Engineer (L3)",
            "employeeHireDate": "2024-03-01T00:00:00Z",
            "managerLdap": "bob",
        })

        self.assertTrue(profile.account_enabled)


if __name__ == "__main__":
    unittest.main()
