"""Caches leave-relevant employment facts from Azure into Redis.

Runs inside the existing daily `update-ldap` cronjob. Azure stays the only
source; the Redis copy is a cache the accrual engine reads so it never calls
Graph.

This is also where a change of annual entitlement is noticed. Azure keeps only
the current job title, so the engine would otherwise have no way to tell a
promotion from a run that never happened, and would pay an L1 promoted in July
for the six months they spent on no entitlement. Comparing tonight's profile
against last night's is the cheapest place to see it.

Profiles live under their own key. The `ldap:{status}:{group}` hashes map ldap to
display name and are read in several places, so widening their values would
break every reader.
"""

import json
from dataclasses import dataclass
from decimal import Decimal

from backend.common.constants import (
    LDAP_KEY_TEMPLATE,
    MicrosoftAccountStatus,
    MicrosoftGroups,
)
from backend.common.leave_enums import LeaveEntryType
from backend.entity.leave_ledger_entity import LeaveLedgerEntity
from backend.leave.coverage_report import CoverageReport, build_coverage_report
from backend.leave.leave_clock import business_today
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


@dataclass(frozen=True)
class _EntitlementChange:
    """Somebody whose annual entitlement moved between two nights."""

    ldap: str
    old_level: str
    new_level: str


class EmploymentSyncService:
    """Refreshes the cached employment profiles used by the leave engine."""

    def __init__(
        self,
        logger,
        redis_client,
        microsoft_service,
        retry_utils,
        database,
        leave_ledger_repository,
        participant_resolver,
    ):
        """Initializes the service.

        Args:
            logger: Logger instance.
            redis_client: Redis client instance.
            microsoft_service: MicrosoftService instance for Graph access.
            retry_utils: RetryUtils for transient Redis failures.
            database: Async session provider, for recording level changes.
            leave_ledger_repository (LeaveLedgerRepository): Ledger writes.
            participant_resolver (LeaveParticipantResolver): ldap to account.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.microsoft_service = microsoft_service
        self.retry_utils = retry_utils
        self.database = database
        self.leave_ledger_repository = leave_ledger_repository
        self.participant_resolver = participant_resolver

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

        await self._write_profiles(in_scope)
        return report

    def _read_employee_ldaps(self) -> frozenset[str]:
        """Reads active `employees` group membership out of Redis."""
        members = self.retry_utils.get_retry_on_transient(
            self.redis_client.hgetall, EMPLOYEES_GROUP_KEY
        )
        return frozenset(members or {})

    async def _write_profiles(self, in_scope: list[dict]) -> None:
        """Writes changed profiles and drops anyone no longer in scope.

        A change of entitlement is recorded on the ledger first, before Redis is
        overwritten. Detection compares tonight's profile against last night's,
        so overwriting first and then failing on the database would erase the
        evidence and the change would never be noticed again. The other way
        round the worst case is a second row on the same day, which the engine
        reads through a maximum and so cannot double-count.
        """
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

        await self._record_entitlement_changes(_entitlement_changes(cached, latest))

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

    async def _record_entitlement_changes(
        self, changes: list[_EntitlementChange]
    ) -> None:
        """Appends a zero-hour ledger row per entitlement change.

        The row is read for its date, not its amount: carrying no hours is what
        lets a balance stay the plain sum of every row, with no type filter for
        a reader to forget. Anyone without a purrf account cannot have a row
        pointing at them, so they are named in a warning instead.

        Args:
            changes: Detected changes, in ldap order.
        """
        if not changes:
            return

        async with self.database.session() as session:
            resolved = await self.participant_resolver.resolve(
                session, [change.ldap for change in changes]
            )
            entries = [
                LeaveLedgerEntity(
                    user_id=resolved.by_ldap[change.ldap],
                    entry_type=LeaveEntryType.LEVEL_CHANGE,
                    hours=Decimal("0.00"),
                    effective_date=business_today(),
                    note=f"{change.old_level} -> {change.new_level}",
                )
                for change in changes
                if change.ldap in resolved.by_ldap
            ]
            if entries:
                await self.leave_ledger_repository.add_entries(session, entries)
                await session.commit()
                self.logger.info(
                    "Recorded %s leave entitlement change(s): %s",
                    len(entries),
                    ", ".join(
                        f"{change.ldap} {change.old_level}->{change.new_level}"
                        for change in changes
                        if change.ldap in resolved.by_ldap
                    ),
                )

        unwritable = [
            change.ldap for change in changes if change.ldap not in resolved.by_ldap
        ]
        if unwritable:
            self.logger.warning(
                "Leave entitlement changed for %s, who have no purrf account to "
                "record it against. Their accrual will be computed as if the "
                "level had always been the new one.",
                ", ".join(unwritable),
            )

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


def _entitlement_changes(cached: dict, latest: dict) -> list[_EntitlementChange]:
    """Finds whose annual entitlement moved between the two nights.

    Three cases deliberately produce nothing, all of them erring towards
    over-paying, which is visible in a balance, rather than under-paying, which
    is not:

    * **A first sighting.** Nothing to compare against, and treating an arrival
      as a change would start their accrual today and lose the year to date.
    * **A title that stopped parsing.** It yields 0h, which looks exactly like a
      demotion; acting on it would freeze that person's accrual until somebody
      noticed.
    * **A title that started parsing.** The mirror image -- a typo being fixed.
      Recording it would restart the proportion today and drop the hours they
      should already have had.

    A move between L2, L3 and L4 also produces nothing: they share an
    entitlement, so there is no proportion to split.

    Args:
        cached: Last night's profiles, ldap to JSON text.
        latest: Tonight's, in the same shape.

    Returns:
        The changes, in ldap order.
    """
    changes = []
    for ldap in sorted(latest):
        if ldap not in cached:
            continue
        try:
            before = json.loads(cached[ldap])
            after = json.loads(latest[ldap])
        except (TypeError, ValueError):
            continue

        if before.get("level") is None or after.get("level") is None:
            continue
        if before.get("annual_hours") == after.get("annual_hours"):
            continue

        changes.append(
            _EntitlementChange(
                ldap=ldap,
                old_level=before["level"],
                new_level=after["level"],
            )
        )
    return changes
