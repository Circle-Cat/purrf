export const API_ENDPOINTS = {
  MY_PROFILE: "/profiles/me",
  MY_PERMISSIONS: "/permissions/me",
  EMAIL_ADD: "/auth/emails/add",
  EMAIL_REMOVE: (emailId) => `/auth/emails/${emailId}`,
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
