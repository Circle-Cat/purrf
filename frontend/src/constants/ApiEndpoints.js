export const API_ENDPOINTS = {
  MY_PROFILE: "/profiles/me",
  MY_PERMISSIONS: "/permissions/me",
  EMAIL_OTP_INITIATE: "/auth/emails/initiate",
  EMAIL_OTP_VERIFY: "/auth/emails/verify",
  EMAIL_LIST: "/auth/emails",
  EMAIL_SET_PRIMARY_INITIATE: (emailId) =>
    `/auth/emails/${emailId}/primary/initiate`,
  EMAIL_SET_PRIMARY_CONFIRM: (emailId) =>
    `/auth/emails/${emailId}/primary/confirm`,
  EMAIL_UNLINK_INITIATE: (identityId) =>
    `/auth/identities/${identityId}/unlink/initiate`,
  EMAIL_UNLINK_CONFIRM: (identityId) =>
    `/auth/identities/${identityId}/unlink/confirm`,
  MENTORSHIP_REGISTRATION: (roundId) =>
    `/mentorship/rounds/${roundId}/registration`,
  MENTORSHIP_MATCH_RESULT: (roundId) => `/mentorship/rounds/${roundId}/matches`,
  MENTORSHIP_FEEDBACK: (roundId) => `/mentorship/rounds/${roundId}/feedback`,
  MENTORSHIP_PARTNERS: "/mentorship/partners/me",
  MENTORSHIP_ROUNDS: "/mentorship/rounds",
  MENTORSHIP_ADMIN_PARTICIPANTS: "/mentorship/admin/participants",
  MENTORSHIP_MEETINGS_ENDPOINT: "/mentorship/v1/meetings",
  MY_INTERNAL_ACTIVITY_SUMMARY: "/summary/me",
  MENTORSHIP_MEETINGS_V2: "/mentorship/v2/meetings",
  MENTORSHIP_MEETING_V2_SINGLE: (meetingId) =>
    `/mentorship/v2/meetings/${meetingId}`,
  MENTORSHIP_MEETING_V2_BATCH_DELETE: "/mentorship/v2/meetings/batch-delete",
  ADMIN_PERMISSIONS: "/admin/permissions",
  ADMIN_USERS: "/admin/users",
  ADMIN_USER_PERMISSIONS: (userId) => `/admin/users/${userId}/permissions`,
  ADMIN_PERMISSION_USERS: (name) => `/admin/permissions/${name}/users`,
  ADMIN_AUDIT_PERMISSION_CHANGES: "/admin/audit/permission-changes",
  ADMIN_USER_GRANT: (userId) => `/admin/users/${userId}/permissions/grant`,
  ADMIN_USER_REVOKE: (userId) => `/admin/users/${userId}/permissions/revoke`,
  ADMIN_USER_SUPER_ADMIN: (userId) => `/admin/users/${userId}/super-admin`,
  RECRUITING_JOBS: "/recruiting/jobs",
  RECRUITING_JOB: (jobId) => `/recruiting/jobs/${jobId}`,
  RECRUITING_JOB_SUBMIT: (jobId) => `/recruiting/jobs/${jobId}/submit`,
  RECRUITING_JOB_CLOSE: (jobId) => `/recruiting/jobs/${jobId}/close`,
  RECRUITING_JOB_REQUEST_CLOSE: (jobId) =>
    `/recruiting/jobs/${jobId}/request-close`,
  RECRUITING_JOB_REQUEST_REOPEN: (jobId) =>
    `/recruiting/jobs/${jobId}/request-reopen`,
  RECRUITING_APPROVERS: "/recruiting/approvers",
  RECRUITING_REVIEWS: "/recruiting/reviews",
  RECRUITING_REVIEW: (reviewId) => `/recruiting/reviews/${reviewId}`,
  RECRUITING_INTERVIEW_POOL: "/recruiting/interview-pool",
  RECRUITING_JOB_OWNERS: "/recruiting/job-owners",
  RECRUITING_PUBLIC_JOB: (jobId) => `/recruiting/public/jobs/${jobId}`,
  RECRUITING_PUBLIC_JOBS: "/recruiting/public/jobs",
  RECRUITING_RESUMES: "/recruiting/resumes",
  RECRUITING_APPLICATIONS: "/recruiting/applications",
  RECRUITING_APPLICATION: (applicationId) =>
    `/recruiting/applications/${applicationId}`,
  RECRUITING_APPLICATIONS_MINE: "/recruiting/applications/mine",
  RECRUITING_MY_APPLICATIONS: "/recruiting/my-applications",
  RECRUITING_BOARD_JOBS: "/recruiting/board/jobs",
  RECRUITING_JOB_BOARD: (jobId) => `/recruiting/jobs/${jobId}/board`,
  RECRUITING_APPLICATION_STAGE: (id) => `/recruiting/applications/${id}/stage`,
  RECRUITING_APPLICATION_SUB_STATUS: (id) =>
    `/recruiting/applications/${id}/sub-status`,
  RECRUITING_APPLICATION_ROUND: (id) => `/recruiting/applications/${id}/round`,
  RECRUITING_APPLICATION_RESUME: (id) =>
    `/recruiting/applications/${id}/resume`,
  RECRUITING_APPLICATION_ASSIGNMENT: (id) =>
    `/recruiting/applications/${id}/assignment`,
  RECRUITING_BLACKLIST: "/recruiting/blacklist",
  RECRUITING_BLACKLIST_UNBLOCK: (userId) => `/recruiting/blacklist/${userId}`,
  RECRUITING_APPLICATION_EVALUATION: (id) =>
    `/recruiting/applications/${id}/evaluation`,
  RECRUITING_EVALUATIONS_MINE: "/recruiting/evaluations/mine",
  RECRUITING_APPLICATION_EVALUATIONS: (id) =>
    `/recruiting/applications/${id}/evaluations`,
  RECRUITING_APPLICATION_ACTIVITY: (id) =>
    `/recruiting/applications/${id}/activity`,
  RECRUITING_APPLICATION_COMMENTS: (id) =>
    `/recruiting/applications/${id}/comments`,
  RECRUITING_APPLICATION_MENTIONABLE_USERS: (id) =>
    `/recruiting/applications/${id}/mentionable-users`,
  RECRUITING_APPLICATION_OTHER_APPLICATIONS: (id) =>
    `/recruiting/applications/${id}/other-applications`,
  RECRUITING_AUDIT_OVERVIEW: "/recruiting/audit/overview",
  RECRUITING_NOTIFICATIONS: "/recruiting/notifications",
  RECRUITING_NOTIFICATION_READ: (id) => `/recruiting/notifications/${id}/read`,
  RECRUITING_NOTIFICATIONS_READ_ALL: "/recruiting/notifications/read-all",
};

/**
 * Query parameter values for the `/profiles/me` API.
 */
export const ProfileFields = Object.freeze({
  USER: "user",
  WORK_HISTORY: "workHistory",
  EDUCATION: "education",
  TRAINING: "training",
});
