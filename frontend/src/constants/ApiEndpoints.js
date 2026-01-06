export const API_ENDPOINTS = {
  MY_PROFILE: "/profiles/me",
  MY_ROLES: "/roles/me",
  MENTORSHIP_REGISTRATION: (roundId) =>
    `/mentorship/rounds/${roundId}/registration`,
  MENTORSHIP_PARTNERS: "/mentorship/partners/me",
  MENTORSHIP_ROUNDS: "/mentorship/rounds",
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
