/**
 * Who owes feedback for a round, and the per-round figures the rounds table
 * shows. Shared by the table's Feedback column and the round's feedback page
 * so the count on the link is the count the page opens.
 */

/**
 * The people a round's feedback is asked of: in a pair this round (going or
 * ended), not withdrawn, not blocked. Counting every registration would show
 * a list of people who were never asked.
 *
 * @param {object} round
 * @param {Array<object>} participants - Every round's participant rows.
 * @param {Array<object>} pairs - Every round's pairs.
 * @param {(userId: number) => {isBlocked: boolean}} accountOf
 * @returns {Array<object>} Their participant rows.
 */
export const feedbackOwedBy = (round, participants, pairs, accountOf) =>
  participants.filter(
    (p) =>
      p.roundId === round.id &&
      p.approvalStatus !== "withdrawn" &&
      !accountOf(p.userId).isBlocked &&
      pairs.some(
        (x) =>
          x.roundId === round.id &&
          (x.mentorId === p.userId || x.menteeId === p.userId),
      ),
  );

const average = (values) =>
  values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;

/**
 * The rounds table's figures for one round, as main's table shows them.
 *
 * @param {object} round
 * @param {Array<object>} participants
 * @param {Array<object>} pairs
 * @param {Object<string, object>} feedback - Keyed by participant id.
 * @returns {{matchedParticipants: number, mentorRating: number|null,
 *   menteeRating: number|null, completedMeetings: number,
 *   avgMeetingsPerPair: number|null}}
 */
export const roundFigures = (round, participants, pairs, feedback) => {
  const roundPairs = pairs.filter((x) => x.roundId === round.id);
  const matched = new Set(roundPairs.flatMap((x) => [x.mentorId, x.menteeId]));
  const ratingOf = (role) =>
    average(
      participants
        .filter(
          (p) =>
            p.roundId === round.id &&
            p.role === role &&
            feedback[p.participantId]?.programRating != null,
        )
        .map((p) => feedback[p.participantId].programRating),
    );
  const completedMeetings = roundPairs.reduce(
    (sum, x) => sum + (x.completed ?? 0),
    0,
  );
  const activePairs = roundPairs.filter((x) => x.status === "active").length;
  return {
    matchedParticipants: matched.size,
    mentorRating: ratingOf("mentor"),
    menteeRating: ratingOf("mentee"),
    completedMeetings,
    avgMeetingsPerPair: activePairs ? completedMeetings / activePairs : null,
  };
};
