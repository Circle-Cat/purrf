/**
 * Calculate mentorship slots for registration and feedback actions.
 *
 * This function determines:
 * - which mentorship round (if any) is currently in the feedback phase
 * - which mentorship round should be shown for registration or viewing
 *
 * Business rules:
 * 1. Feedback slot:
 *    - A round is considered in the feedback phase if today is between
 *      `meetingsCompletionDeadlineAt` and `feedbackDeadlineAt` (inclusive).
 *
 * 2. Registration / view slot:
 *    - Prefer a round that is currently open for registration.
 *    - If none is open, fall back to the most recently started round
 *      (used for "view only" purposes).
 *
 * @param {Array<Object>} allRounds - All mentorship rounds.
 * @param {Object} allRounds[].timeline - Timeline information of a round.
 * @returns {{
 *   feedbackRoundId: string | null,
 *   isFeedbackEnabled: boolean,
 *   regRoundId: string | null,
 *   isRegistrationOpen: boolean
 * }}
 */
export const calculateMentorshipSlots = (allRounds) => {
  // Get today's date in YYYY-MM-DD format
  const today = new Date().toISOString().split("T")[0];

  // Sort rounds by promotionStartAt in descending order (latest first)
  // and filter out invalid rounds without promotionStartAt
  const sorted = [...allRounds]
    .filter((r) => r.timeline?.promotionStartAt)
    .sort((a, b) =>
      b.timeline.promotionStartAt.localeCompare(a.timeline.promotionStartAt),
    );

  /**
   * 1. Find the feedback slot:
   * A round is in the feedback phase if today is after meetings are completed
   * and before the feedback deadline.
   */
  const feedbackRound = sorted.find(
    (r) =>
      today >= r.timeline.meetingsCompletionDeadlineAt &&
      today <= r.timeline.feedbackDeadlineAt,
  );

  /**
   * 2. Find the registration / view slot:
   *
   * - currentRegRound:
   *   A round that is currently open for registration.
   *
   * - lastStartedRound:
   *   The most recently started round, used as a fallback for "view only"
   *   when registration is already closed.
   */
  const currentRegRound = sorted.find(
    (r) =>
      today >= r.timeline.promotionStartAt &&
      today < r.timeline.applicationDeadlineAt,
  );

  const lastStartedRound = sorted.find(
    (r) => today >= r.timeline.promotionStartAt,
  );

  return {
    // Controls the "Feedback" button
    feedbackRoundId: feedbackRound?.id || null,
    isFeedbackEnabled: Boolean(feedbackRound),

    // Controls the "Register" / "View" button
    regRoundId: currentRegRound?.id || lastStartedRound?.id || null,
    isRegistrationOpen: Boolean(currentRegRound), // true = "Register", false = "View"
  };
};
