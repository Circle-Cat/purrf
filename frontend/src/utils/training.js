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
