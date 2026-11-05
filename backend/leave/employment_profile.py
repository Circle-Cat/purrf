"""Derives leave-relevant employment facts from a Graph user payload.

The three ways a payload can be imperfect behave differently on purpose:

* A non-SWE job title yields 0h and raises nothing -- expected, not a gap.
* A field the engine needs is missing or malformed: reported for an admin to
  chase. Silently skipping accrual surfaces months later, once the ledger is
  frozen and unrebuildable.
* A missing manager is reported and additionally blocks every request type,
  sick leave included.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

FULL_TIME_EMPLOYEE_TYPE = "Full-time Employee"
CHINA_OFFICE_LOCATION_PREFIX = "CN-"

BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")

_SWE_JOB_TITLE_PATTERN = re.compile(r"^software\s+engineer\s*\(\s*(l[1-4])\s*\)$")
_LEVEL_SHAPED_JOB_TITLE_PATTERN = re.compile(r"^software\s+engineer\s*\(", re.I)

ANNUAL_HOURS_BY_LEVEL = {
    "L1": 0,
    "L2": 80,
    "L3": 80,
    "L4": 80,
}


class ProfileProblem(str, Enum):
    """A data gap an admin has to resolve. Never raised for expected cases."""

    MISSING_HIRE_DATE = "missing_hire_date"
    MISSING_MANAGER = "missing_manager"
    UNPARSEABLE_JOB_TITLE = "unparseable_job_title"


@dataclass(frozen=True)
class EmploymentProfile:
    """Leave-relevant facts about one person, derived and never stored."""

    ldap: str
    level: str | None
    annual_hours: int
    hire_date: str | None
    leave_date: str | None
    manager_ldap: str | None
    # The accrual engine's fallback for "has left". A leaver is supposed to
    # carry a leave date and one of the five China full-timers is disabled
    # without one, so on the leave date alone that person would accrue for
    # good. A payload missing the field counts as enabled: stopping accrual by
    # accident is invisible in a balance, and over-paying is not.
    account_enabled: bool = True
    problems: tuple[ProfileProblem, ...] = field(default=())


def is_in_leave_scope(raw: dict) -> bool:
    """Whether the leave system covers this person, on the Azure evidence alone.

    ``users.is_internal`` is the third admission condition and belongs to the
    purrf row, so the caller checks it; this function never sees it.

    Args:
        raw: A flattened Graph user payload.

    Returns:
        True when they are a full-time employee based in China.
    """
    if raw.get("employeeType") != FULL_TIME_EMPLOYEE_TYPE:
        return False

    office_location = raw.get("officeLocation") or ""
    return office_location.startswith(CHINA_OFFICE_LOCATION_PREFIX)


def parse_level(job_title: str | None) -> tuple[str | None, bool]:
    """Extracts the engineering level out of an Azure ``jobTitle``.

    Args:
        job_title: The raw ``jobTitle`` value, which may be absent.

    Returns:
        A ``(level, malformed)`` pair. ``malformed`` is True only when the title
        looks like it was meant to carry a level but does not parse -- a typo
        worth reporting, unlike a plainly non-engineering title.
    """
    if not job_title:
        return None, False

    normalized = job_title.strip()
    match = _SWE_JOB_TITLE_PATTERN.match(normalized.lower())
    if match:
        return match.group(1).upper(), False

    return None, bool(_LEVEL_SHAPED_JOB_TITLE_PATTERN.match(normalized))


def build_employment_profile(raw: dict) -> EmploymentProfile:
    """Derives one person's leave-relevant employment facts.

    Args:
        raw: A flattened Graph user payload carrying ``mail``, ``jobTitle``,
            ``employeeHireDate``, ``employeeLeaveDateTime`` and ``managerLdap``.

    Returns:
        The derived profile. Problems are reported on it rather than raised, so
        one bad row never aborts a whole sync.
    """
    mail = raw.get("mail") or ""
    ldap = mail.split("@")[0] if "@" in mail else mail

    level, malformed_job_title = parse_level(raw.get("jobTitle"))
    hire_date = _as_date(raw.get("employeeHireDate"))
    leave_date = _as_date(raw.get("employeeLeaveDateTime"))
    manager_ldap = raw.get("managerLdap")

    problems = []
    if malformed_job_title:
        problems.append(ProfileProblem.UNPARSEABLE_JOB_TITLE)
    if not hire_date:
        problems.append(ProfileProblem.MISSING_HIRE_DATE)
    if not manager_ldap:
        problems.append(ProfileProblem.MISSING_MANAGER)

    return EmploymentProfile(
        ldap=ldap,
        level=level,
        annual_hours=ANNUAL_HOURS_BY_LEVEL.get(level, 0),
        hire_date=hire_date,
        leave_date=leave_date,
        manager_ldap=manager_ldap,
        account_enabled=raw.get("accountEnabled") is not False,
        problems=tuple(problems),
    )


def _as_date(raw_value: str | None) -> str | None:
    """Reduces a Graph timestamp to its Beijing calendar date.

    Azure stores these as instants, and a Beijing midnight arrives as 16:00 the
    previous day in UTC. Truncating the string would put every such hire date a
    day early -- and the hire date is where accrual starts counting.

    A value carrying no timezone is taken as already being the local date.
    """
    if not raw_value:
        return None

    try:
        moment = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return raw_value.split("T")[0]

    if moment.tzinfo is None:
        return moment.date().isoformat()

    return moment.astimezone(BUSINESS_TIMEZONE).date().isoformat()
