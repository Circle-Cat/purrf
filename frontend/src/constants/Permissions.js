/**
 * Frontend mirror of the backend `Permission` enum values used to gate UI.
 * Only the permissions the frontend actually checks live here; the backend
 * `/permissions/me` returns the full resolved set.
 */
export const PERMISSIONS = {
  INTERNAL_ACTIVITY_READ: "internal_activity.read",
  DASHBOARD_ACTIVITY_SUMMARY_READ: "dashboard.activity_summary.read",
  MENTORSHIP_MANAGEMENT_READ: "mentorship.management.read",
  MENTORSHIP_PARTICIPANT_READ: "mentorship.participant.read",
  MENTORSHIP_ROUND_READ: "mentorship.round.read",
  MENTORSHIP_ROUND_WRITE: "mentorship.round.write",
  PERMISSION_MANAGE: "permission.manage",
  SUPER_ADMIN_REVOKE: "super_admin.revoke",
  RECRUITING_JOB_READ: "recruiting.job.read",
  RECRUITING_JOB_WRITE: "recruiting.job.write",
  RECRUITING_JOB_APPROVE: "recruiting.job.approve",
  RECRUITING_BLACKLIST_WRITE: "recruiting.blacklist.write",
  RECRUITING_AUDIT_READ: "recruiting.audit.read",
};
