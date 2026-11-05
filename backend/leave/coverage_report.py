"""Reports what Azure actually holds for the people the leave system covers.

Coverage is measured over in-scope people only. An intern with no hire date is
not a gap -- counting them would hide the real ones.
"""

from dataclasses import dataclass

from backend.leave.employment_profile import (
    CHINA_OFFICE_LOCATION_PREFIX,
    FULL_TIME_EMPLOYEE_TYPE,
    ProfileProblem,
    build_employment_profile,
    is_in_leave_scope,
)

TRACKED_FIELDS = (
    "jobTitle",
    "officeLocation",
    "employeeType",
    "employeeHireDate",
    "managerLdap",
)

ADMISSION_FIELDS = ("employeeType", "officeLocation")

NO_LEVEL_KEY = "none"


@dataclass(frozen=True)
class CoverageReport:
    """What Graph returned, and who needs their record fixed.

    Attributes:
        fetched_count: Every user Graph returned, in scope or not.
        in_scope_count: Those the leave system covers.
        field_coverage: Field name to ``(present, total)``, over in-scope people.
        level_distribution: Level to headcount, ``"none"`` for titles carrying no
            level.
        blocked_no_manager: Ldaps with no manager in Azure. They cannot submit
            any request at all, so they are listed separately and fixed first.
        needs_attention: Ldap to problems worth chasing, excluding the
            missing-manager case above.
        unknown_eligibility: Ldap to the blank admission fields that stop
            eligibility being decided. These people are excluded from the leave
            system and this is the only place that says so.
    """

    fetched_count: int
    in_scope_count: int
    field_coverage: dict[str, tuple[int, int]]
    level_distribution: dict[str, int]
    blocked_no_manager: list[str]
    needs_attention: dict[str, list[str]]
    unknown_eligibility: dict[str, list[str]]


def build_coverage_report(
    employee_ldaps: frozenset[str], raw_users: list[dict]
) -> CoverageReport:
    """Summarises employment-field completeness across a fetched roster.

    Args:
        employee_ldaps: Ldaps in the Microsoft 365 ``employees`` group. Not the
            same as full-time -- part-timers are in there too -- but it
            establishes an employment relationship, which is what makes a blank
            admission field worth chasing.
        raw_users: Flattened Graph user payloads for the whole directory.
            Out-of-scope users count toward ``fetched_count`` only.

    Returns:
        The assembled report.
    """
    in_scope = [raw for raw in raw_users if is_in_leave_scope(raw)]

    field_coverage = {
        field: (sum(1 for raw in in_scope if raw.get(field)), len(in_scope))
        for field in TRACKED_FIELDS
    }

    level_distribution: dict[str, int] = {}
    blocked_no_manager = []
    needs_attention: dict[str, list[str]] = {}

    for raw in in_scope:
        profile = build_employment_profile(raw)

        level_key = profile.level or NO_LEVEL_KEY
        level_distribution[level_key] = level_distribution.get(level_key, 0) + 1

        if ProfileProblem.MISSING_MANAGER in profile.problems:
            blocked_no_manager.append(profile.ldap)

        other_problems = [
            problem.value
            for problem in profile.problems
            if problem is not ProfileProblem.MISSING_MANAGER
        ]
        if other_problems:
            needs_attention[profile.ldap] = other_problems

    return CoverageReport(
        fetched_count=len(raw_users),
        in_scope_count=len(in_scope),
        field_coverage=field_coverage,
        level_distribution=level_distribution,
        blocked_no_manager=sorted(blocked_no_manager),
        needs_attention=needs_attention,
        unknown_eligibility=_find_unknown_eligibility(employee_ldaps, raw_users),
    )


def _find_unknown_eligibility(
    employee_ldaps: frozenset[str], raw_users: list[dict]
) -> dict[str, list[str]]:
    """Finds employees whose eligibility cannot be decided from blank fields.

    A blank is only reported when filling it in could change the outcome, so the
    list stays actionable.
    """
    unknown = {}

    for raw in raw_users:
        mail = raw.get("mail") or ""
        ldap = mail.split("@")[0] if "@" in mail else mail

        if ldap not in employee_ldaps or is_in_leave_scope(raw):
            continue

        blanks = [field for field in ADMISSION_FIELDS if not raw.get(field)]
        if blanks and not _ruled_out_by_a_known_field(raw):
            unknown[ldap] = blanks

    return unknown


def _ruled_out_by_a_known_field(raw: dict) -> bool:
    """Whether a field that IS filled in already makes this person ineligible."""
    employee_type = raw.get("employeeType")
    if employee_type and employee_type != FULL_TIME_EMPLOYEE_TYPE:
        return True

    office_location = raw.get("officeLocation")
    return bool(
        office_location and not office_location.startswith(CHINA_OFFICE_LOCATION_PREFIX)
    )
