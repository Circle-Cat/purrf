from enum import StrEnum


class Permission(StrEnum):
    """
    Endpoint authorization unit (permission system).

    Permissions are a code enum, not a DB table: they are a code-to-endpoint
    contract, so a typo fails at startup rather than at runtime. Per-user grants
    live in the user_permissions table (one row per granted permission);
    super_admin and service accounts resolve to the code-constant bundles below
    instead of carrying rows.
    """

    SYSTEM_BACKFILL = "system.backfill"
    SYSTEM_BACKFILL_SCHEDULED = "system.backfill.scheduled"
    SYSTEM_SYNC = "system.sync"
    SYSTEM_SUBSCRIBE = "system.subscribe"
    INTERNAL_ACTIVITY_READ = "internal_activity.read"
    DIRECTORY_MICROSOFT_LDAP_READ = "directory.microsoft_ldap.read"
    DASHBOARD_ACTIVITY_SUMMARY_READ = "dashboard.activity_summary.read"
    MENTORSHIP_MANAGEMENT_READ = "mentorship.management.read"
    MENTORSHIP_ROUND_READ = "mentorship.round.read"
    MENTORSHIP_ROUND_WRITE = "mentorship.round.write"
    MENTORSHIP_APPLICATION_REVIEW = "mentorship.application.review"
    MENTORSHIP_PARTICIPANT_READ = "mentorship.participant.read"
    MENTORSHIP_PARTICIPANT_WRITE = "mentorship.participant.write"
    PERMISSION_MANAGE = "permission.manage"
    SUPER_ADMIN_REVOKE = "super_admin.revoke"


# Auto-injected for internal employees by the lifecycle hook on first internal
# login (granted_source='system_internal') and revoked when the internal
# identity is removed. This constant is the source of truth; changing it needs a
# migration to sync existing system_internal rows.
INTERNAL_EMPLOYEE_PERMISSIONS = frozenset({
    Permission.DIRECTORY_MICROSOFT_LDAP_READ,
    Permission.DASHBOARD_ACTIVITY_SUMMARY_READ,
})

# Service accounts have no users row to anchor a lifecycle hook, so
# resolve_permissions returns this code constant directly — the one runtime
# injection path retained.
SERVICE_ACCOUNT_PERMISSIONS = frozenset({
    Permission.SYSTEM_BACKFILL_SCHEDULED,
    Permission.SYSTEM_SYNC,
})

# users.is_super_admin = true resolves to the full enum without expanding rows
# in user_permissions, so a super_admin can never be left half-revoked.
SUPER_ADMIN_PERMISSIONS = frozenset(Permission)
