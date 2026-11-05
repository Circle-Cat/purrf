import unittest

from backend.leave.coverage_report import build_coverage_report

# Every fixture ldap: group membership only decides whose blanks get chased.
EMPLOYEE_LDAPS = frozenset({
    "alice",
    "bea",
    "carl",
    "cody",
    "dana",
    "mo",
    "a",
    "b",
    "c",
    "d",
})


def _raw(**overrides) -> dict:
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


class BuildCoverageReportTest(unittest.TestCase):
    """The PR1 deliverable: what Azure actually holds, and who needs fixing."""

    def test_counts_fetched_and_in_scope_separately(self):
        report = build_coverage_report(
            EMPLOYEE_LDAPS,
            [
                _raw(mail="alice@u.circlecat.org"),
                _raw(mail="carl@u.circlecat.org", employeeType="Intern"),
                _raw(mail="dana@u.circlecat.org", officeLocation="US-CA-SFO"),
            ],
        )

        self.assertEqual(report.fetched_count, 3)
        self.assertEqual(report.in_scope_count, 1)

    def test_field_coverage_is_measured_over_in_scope_people_only(self):
        """An intern with no hire date must not drag the numbers down."""
        report = build_coverage_report(
            EMPLOYEE_LDAPS,
            [
                _raw(mail="alice@u.circlecat.org"),
                _raw(
                    mail="carl@u.circlecat.org",
                    employeeType="Intern",
                    employeeHireDate=None,
                ),
            ],
        )

        self.assertEqual(report.field_coverage["employeeHireDate"], (1, 1))

    def test_field_coverage_reports_present_over_total(self):
        report = build_coverage_report(
            EMPLOYEE_LDAPS,
            [
                _raw(mail="alice@u.circlecat.org"),
                _raw(mail="bea@u.circlecat.org", employeeHireDate=None),
            ],
        )

        self.assertEqual(report.field_coverage["employeeHireDate"], (1, 2))
        self.assertEqual(report.field_coverage["jobTitle"], (2, 2))

    def test_people_missing_a_manager_are_listed_separately_and_first(self):
        """These people cannot submit anything at all, so they outrank the rest."""
        report = build_coverage_report(
            EMPLOYEE_LDAPS,
            [
                _raw(mail="alice@u.circlecat.org", managerLdap=None),
                _raw(mail="bea@u.circlecat.org", employeeHireDate=None),
            ],
        )

        self.assertEqual(report.blocked_no_manager, ["alice"])
        self.assertNotIn("alice", report.needs_attention)

    def test_other_problems_are_listed_with_their_reasons(self):
        report = build_coverage_report(
            EMPLOYEE_LDAPS,
            [
                _raw(mail="bea@u.circlecat.org", employeeHireDate=None),
                _raw(mail="cody@u.circlecat.org", jobTitle="Software Engineer (L9)"),
            ],
        )

        self.assertEqual(
            report.needs_attention,
            {
                "bea": ["missing_hire_date"],
                "cody": ["unparseable_job_title"],
            },
        )

    def test_a_non_swe_title_is_not_flagged_for_attention(self):
        """0h entitlement is the intended outcome, not a data problem."""
        report = build_coverage_report(
            EMPLOYEE_LDAPS, [_raw(mail="mo@u.circlecat.org", jobTitle="Office Manager")]
        )

        self.assertEqual(report.needs_attention, {})
        self.assertEqual(report.blocked_no_manager, [])

    def test_level_distribution_is_counted(self):
        report = build_coverage_report(
            EMPLOYEE_LDAPS,
            [
                _raw(mail="a@u.circlecat.org", jobTitle="Software Engineer (L1)"),
                _raw(mail="b@u.circlecat.org", jobTitle="Software Engineer (L3)"),
                _raw(mail="c@u.circlecat.org", jobTitle="Software Engineer (L3)"),
                _raw(mail="d@u.circlecat.org", jobTitle="Office Manager"),
            ],
        )

        self.assertEqual(report.level_distribution["L1"], 1)
        self.assertEqual(report.level_distribution["L3"], 2)
        self.assertEqual(report.level_distribution["none"], 1)

    def test_an_empty_roster_reports_zeroes_rather_than_dividing_by_zero(self):
        report = build_coverage_report(EMPLOYEE_LDAPS, [])

        self.assertEqual(report.fetched_count, 0)
        self.assertEqual(report.in_scope_count, 0)
        self.assertEqual(report.field_coverage["jobTitle"], (0, 0))
        self.assertEqual(report.needs_attention, {})


class UnknownEligibilityTest(unittest.TestCase):
    """Employees whose admission fields are blank, so eligibility is undecidable.

    Without this section the exclusion is invisible: a China full-timer whose
    `employeeType` was never filled in would silently never accrue an hour.
    """

    def test_a_blank_employee_type_on_an_employee_is_reported(self):
        report = build_coverage_report(
            frozenset({"alice"}),
            [_raw(mail="alice@u.circlecat.org", employeeType=None)],
        )

        self.assertEqual(report.unknown_eligibility, {"alice": ["employeeType"]})

    def test_a_blank_office_location_on_an_employee_is_reported(self):
        report = build_coverage_report(
            frozenset({"alice"}),
            [_raw(mail="alice@u.circlecat.org", officeLocation=None)],
        )

        self.assertEqual(report.unknown_eligibility, {"alice": ["officeLocation"]})

    def test_both_blank_reports_both_fields(self):
        report = build_coverage_report(
            frozenset({"alice"}),
            [
                _raw(
                    mail="alice@u.circlecat.org", employeeType=None, officeLocation=None
                )
            ],
        )

        self.assertEqual(
            report.unknown_eligibility, {"alice": ["employeeType", "officeLocation"]}
        )

    def test_a_blank_field_outside_the_employees_group_is_not_reported(self):
        """A volunteer with no employeeType is not a gap anybody needs to fix."""
        report = build_coverage_report(
            frozenset(),
            [_raw(mail="vera@u.circlecat.org", employeeType=None)],
        )

        self.assertEqual(report.unknown_eligibility, {})

    def test_a_known_disqualifying_value_is_not_reported(self):
        """`Intern` is an answer, not a gap. Nothing to chase."""
        report = build_coverage_report(
            frozenset({"carl"}),
            [_raw(mail="carl@u.circlecat.org", employeeType="Intern")],
        )

        self.assertEqual(report.unknown_eligibility, {})

    def test_a_blank_field_that_cannot_change_the_outcome_is_not_reported(self):
        """Office is known to be outside China, so employeeType cannot change it."""
        report = build_coverage_report(
            frozenset({"dana"}),
            [
                _raw(
                    mail="dana@u.circlecat.org",
                    employeeType=None,
                    officeLocation="US-CA-SFO",
                )
            ],
        )

        self.assertEqual(report.unknown_eligibility, {})

    def test_an_in_scope_person_is_never_listed_as_unknown(self):
        report = build_coverage_report(
            frozenset({"alice"}), [_raw(mail="alice@u.circlecat.org")]
        )

        self.assertEqual(report.unknown_eligibility, {})
        self.assertEqual(report.in_scope_count, 1)


if __name__ == "__main__":
    unittest.main()
