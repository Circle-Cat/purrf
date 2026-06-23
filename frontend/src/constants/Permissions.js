/**
 * Frontend mirror of the backend `Permission` enum values used to gate UI.
 * Only the permissions the frontend actually checks live here; the backend
 * `/permissions/me` returns the full resolved set.
 */
export const PERMISSIONS = {
  INTERNAL_ACTIVITY_READ: "internal_activity.read",
  DASHBOARD_ACTIVITY_SUMMARY_READ: "dashboard.activity_summary.read",
  MENTORSHIP_MANAGEMENT_READ: "mentorship.management.read",
  MENTORSHIP_ROUND_READ: "mentorship.round.read",
  MENTORSHIP_ROUND_WRITE: "mentorship.round.write",
  RECRUITING_JOB_READ: "recruiting.job.read",
  RECRUITING_JOB_WRITE: "recruiting.job.write",
  RECRUITING_APPLICATION_READ: "recruiting.application.read",
  RECRUITING_APPLICATION_ADVANCE: "recruiting.application.advance",
};
