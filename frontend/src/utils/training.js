/**
 * Training categories whose completion is a hard prerequisite for
 * mentorship matching. Surfaced to the user via the Personal Dashboard
 * reminder and the highlighted row in TrainingSection.
 */
export const ONBOARDING_TRAINING_CATEGORIES = [
  "mentorship_mentor_onboarding",
  "mentorship_mentee_onboarding",
];

/**
 * Returns true if `training` is one of the mentorship onboarding rows
 * AND has not been completed yet (status !== "done").
 *
 * @param {{category: string, status: string}} training - A training row
 *   from the profile API.
 * @returns {boolean}
 */
export const isIncompleteOnboarding = (training) =>
  ONBOARDING_TRAINING_CATEGORIES.includes(training.category) &&
  training.status !== "done";

/**
 * Whether the mentorship onboarding course is done for every given role.
 * A role with no onboarding row counts as not done.
 *
 * @param {Array<{category: string, status: string}>} training - Training
 *   rows from the profile API.
 * @param {Array<"mentor"|"mentee">} roles - Roles to check.
 * @returns {boolean}
 */
export const isOnboardingDoneForRoles = (training, roles) =>
  roles.length > 0 &&
  roles.every((role) =>
    training.some(
      (row) =>
        row.category === `mentorship_${role}_onboarding` &&
        row.status === "done",
    ),
  );
