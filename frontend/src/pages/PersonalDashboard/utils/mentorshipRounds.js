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

  /**
   *  3. Match Result Logic
   *
   * Goal: Identify the round that is currently in the announcement period.
   * Logic: The current date must fall between `matchNotificationAt` and `feedbackDeadlineAt`.
   */
  const activeMatchRound = sorted.find(
    (r) =>
      r.timeline.matchNotificationAt &&
      today >= r.timeline.matchNotificationAt &&
      today <= r.timeline.feedbackDeadlineAt,
  );
  return {
    // Controls the "Feedback" button
    feedbackRoundId: feedbackRound?.id || null,
    isFeedbackEnabled: Boolean(feedbackRound),

    // Controls the "Register" / "View" button
    regRoundId: currentRegRound?.id || lastStartedRound?.id || null,
    isRegistrationOpen: Boolean(currentRegRound), // true = "Register", false = "View"
    matchResultRoundName:
      activeMatchRound?.name || lastStartedRound?.name || "",

    // Set to true only during the announcement period
    canViewMatch: !!activeMatchRound,
  };
};

/**
 * Compute the display status for all mentorship rounds and identify
 * the default round to show in the participant card.
 *
 * Status rules for each round:
 * - "active": today is between roundStart (matchNotificationAt or promotionStartAt)
 *    and meetingsCompletionDeadlineAt (inclusive).
 * - "upcoming": roundStart is in the future.
 * - "completed": meetingsCompletionDeadlineAt is in the past.
 *
 * activeRoundId priority: active → upcoming → null.
 *
 * @param {Array<Object>} allRounds - All mentorship rounds with timeline data.
 * @returns {{
 *   sortedRounds: Array<Object & { status: "active"|"upcoming"|"completed"|null }>,
 *   activeRoundId: string | null
 * }}
 */
export const calculateRoundStatus = (allRounds) => {
  const today = new Date();
  const sortedRounds = [...allRounds]
    .map((round) => {
      const timeline = round.timeline || {};
      const roundStart = timeline.matchNotificationAt
        ? new Date(timeline.matchNotificationAt)
        : timeline.promotionStartAt
          ? new Date(timeline.promotionStartAt)
          : null;
      const roundEnd = timeline.meetingsCompletionDeadlineAt
        ? new Date(timeline.meetingsCompletionDeadlineAt)
        : null;

      const status =
        roundStart && roundEnd && today >= roundStart && today <= roundEnd
          ? "active"
          : roundStart && today < roundStart
            ? "upcoming"
            : roundEnd && today > roundEnd
              ? "completed"
              : null;

      return {
        ...round,
        status,
        _parsedEnd: roundEnd,
      };
    })
    .sort((a, b) => b._parsedEnd - a._parsedEnd);

  const activeRound =
    sortedRounds.find((r) => r.status === "active") ||
    sortedRounds.find((r) => r.status === "upcoming") ||
    null;

  return {
    sortedRounds,
    activeRoundId: activeRound?.id || null,
  };
};
