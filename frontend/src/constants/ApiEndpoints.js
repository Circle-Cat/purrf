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
  MENTORSHIP_MEETINGS_ENDPOINT: "/mentorship/v1/meetings",
  MY_INTERNAL_ACTIVITY_SUMMARY: "/summary/me",
  MENTORSHIP_MEETINGS_V2: "/mentorship/v2/meetings",
  MENTORSHIP_MEETING_V2_SINGLE: (meetingId) =>
    `/mentorship/v2/meetings/${meetingId}`,
  MENTORSHIP_MEETING_V2_BATCH_DELETE: "/mentorship/v2/meetings/batch-delete",
  RECRUITING_JOBS: "/recruiting/jobs",
  RECRUITING_JOB: (jobId) => `/recruiting/jobs/${jobId}`,
  RECRUITING_JOB_PUBLISH: (jobId) => `/recruiting/jobs/${jobId}/publish`,
  RECRUITING_JOB_CLOSE: (jobId) => `/recruiting/jobs/${jobId}/close`,
  RECRUITING_JOB_APPLICATIONS: (jobId) =>
    `/recruiting/jobs/${jobId}/applications`,
  RECRUITING_JOB_BOARD: (jobId) => `/recruiting/jobs/${jobId}/board`,
  RECRUITING_APPLICATION_VIEW: (applicationId) =>
    `/recruiting/applications/${applicationId}/view`,
  RECRUITING_APPLICATION_ADVANCE: (applicationId) =>
    `/recruiting/applications/${applicationId}/advance`,
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
