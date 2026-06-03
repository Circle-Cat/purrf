export const API_ENDPOINTS = {
  MY_PROFILE: "/profiles/me",
  MY_PERMISSIONS: "/permissions/me",
  EMAIL_OTP_INITIATE: "/auth/emails/initiate",
  EMAIL_OTP_VERIFY: "/auth/emails/verify",
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
