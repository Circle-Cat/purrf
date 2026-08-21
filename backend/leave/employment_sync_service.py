"""Caches leave-relevant employment facts from Azure into Redis.

Runs inside the existing daily `update-ldap` cronjob. Azure stays the only
source; the Redis copy is a cache the accrual engine reads so it never calls
Graph.

Profiles live under their own key. The `ldap:{status}:{group}` hashes map ldap to
display name and are read in several places, so widening their values would
break every reader.
"""

import json

from backend.common.constants import (
    LDAP_KEY_TEMPLATE,
    MicrosoftAccountStatus,
    MicrosoftGroups,
)
from backend.leave.coverage_report import CoverageReport, build_coverage_report
from backend.leave.employment_profile import (
    build_employment_profile,
    is_in_leave_scope,
)

LEAVE_EMPLOYMENT_KEY = "leave:employment"

# Written by MicrosoftMemberSyncService earlier in the same cron run, so reading
# it costs no Graph request. Only the active half matters -- nobody chases data
# on someone who has already left.
EMPLOYEES_GROUP_KEY = LDAP_KEY_TEMPLATE.format(
    account_status=MicrosoftAccountStatus.ACTIVE.value,
    group=MicrosoftGroups.EMPLOYEES.value,
)


class EmploymentSyncService:
    """Refreshes the cached employment profiles used by the leave engine."""

    def __init__(self, logger, redis_client, microsoft_service, retry_utils):
        """Initializes the service.

        Args:
            logger: Logger instance.
            redis_client: Redis client instance.
            microsoft_service: MicrosoftService instance for Graph access.
            retry_utils: RetryUtils for transient Redis failures.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.microsoft_service = microsoft_service
        self.retry_utils = retry_utils

    async def sync_employment_profiles_to_redis(self) -> CoverageReport:
        """Refreshes cached employment profiles and reports field completeness.

        Employee-group membership is read from the Redis hash
        MicrosoftMemberSyncService writes, so that sync has to run first in the
        same request. **Do not reorder or parallelise those two calls.**

        Returns:
            CoverageReport: field coverage plus the people whose records need
                fixing.
        """
        graph_users = await self.microsoft_service.get_all_microsoft_members()
        raw_users = [_flatten(user) for user in graph_users]

        in_scope = [raw for raw in raw_users if is_in_leave_scope(raw)]
        self.logger.info(
            f"Fetched {len(raw_users)} directory users, {len(in_scope)} in leave scope."
        )

        report = build_coverage_report(self._read_employee_ldaps(), raw_users)
        self._log_report(report)

        self._write_profiles(in_scope)
        return report

    def _read_employee_ldaps(self) -> frozenset[str]:
        """Reads active `employees` group membership out of Redis."""
        members = self.retry_utils.get_retry_on_transient(
            self.redis_client.hgetall, EMPLOYEES_GROUP_KEY
        )
        return frozenset(members or {})

    def _write_profiles(self, in_scope: list[dict]) -> None:
        """Writes changed profiles and drops anyone no longer in scope."""
        cached = self.retry_utils.get_retry_on_transient(
            self.redis_client.hgetall, LEAVE_EMPLOYMENT_KEY
        )

        latest = {}
        for raw in in_scope:
            profile = build_employment_profile(raw)
            latest[profile.ldap] = json.dumps(
                {
                    "level": profile.level,
                    "annual_hours": profile.annual_hours,
                    "hire_date": profile.hire_date,
                    "leave_date": profile.leave_date,
                    "manager_ldap": profile.manager_ldap,
                    "account_enabled": profile.account_enabled,
                    "problems": [problem.value for problem in profile.problems],
                },
                sort_keys=True,
            )

        pipe = self.redis_client.pipeline()
        changes_made = False

        stale = set(cached) - set(latest)
        if stale:
            pipe.hdel(LEAVE_EMPLOYMENT_KEY, *sorted(stale))
            changes_made = True
            self.logger.info(f"Dropped {len(stale)} profiles no longer in leave scope.")

        changed = {
            ldap: payload
            for ldap, payload in latest.items()
            if cached.get(ldap) != payload
        }
        if changed:
            pipe.hset(LEAVE_EMPLOYMENT_KEY, mapping=changed)
            changes_made = True
            self.logger.info(f"Wrote {len(changed)} employment profiles.")

        if changes_made:
            self.retry_utils.get_retry_on_transient(pipe.execute)
        else:
            self.logger.info("Employment profiles unchanged, skipping write.")

    def _log_report(self, report: CoverageReport) -> None:
        """Prints the coverage report."""
        self.logger.info(
            f"Leave scope: {report.in_scope_count} of {report.fetched_count} "
            f"directory users. Levels: {report.level_distribution}"
        )

        for field, (present, total) in sorted(report.field_coverage.items()):
            log = self.logger.warning if present < total else self.logger.info
            log(f"Field '{field}' coverage: {present}/{total}")

        if report.blocked_no_manager:
            self.logger.error(
                f"{len(report.blocked_no_manager)} in-scope people have no manager in "
                f"Azure and cannot submit any leave request, including sick leave: "
                f"{', '.join(report.blocked_no_manager)}"
            )

        if report.needs_attention:
            self.logger.error(
                f"{len(report.needs_attention)} in-scope people have unusable "
                f"employment data: {report.needs_attention}"
            )

        if report.unknown_eligibility:
            self.logger.error(
                f"{len(report.unknown_eligibility)} employees have blank admission "
                f"fields, so the leave system is leaving them out. A China full-timer "
                f"could be hiding here: {report.unknown_eligibility}"
            )


def _flatten(graph_user) -> dict:
    """Reduces a Graph SDK user object to the plain payload the parsers expect.

    The SDK is snake_case while the rest of this package speaks Graph field
    names, so the translation happens once, here.
    """
    return {
        "id": graph_user.id,
        "mail": graph_user.mail,
        "jobTitle": graph_user.job_title,
        "officeLocation": graph_user.office_location,
        "employeeType": graph_user.employee_type,
        "accountEnabled": graph_user.account_enabled,
        "employeeHireDate": _as_text(graph_user.employee_hire_date),
        "employeeLeaveDateTime": _as_text(graph_user.employee_leave_date_time),
        "managerLdap": _manager_ldap(graph_user),
    }


def _manager_ldap(graph_user) -> str | None:
    """Derives the approver's ldap from the manager expanded onto the user.

    Absent when nobody is assigned, which is expected data -- recorded as a
    problem on the profile, never raised.
    """
    manager = getattr(graph_user, "manager", None)
    mail = getattr(manager, "mail", None) if manager is not None else None
    if not mail or "@" not in mail:
        return None
    return mail.split("@")[0]


def _as_text(value) -> str | None:
    """Renders a Graph date field as text, whether the SDK typed it or not."""
    if value is None:
        return None
    return value if isinstance(value, str) else value.isoformat()
