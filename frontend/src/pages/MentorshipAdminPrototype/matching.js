import { MATCH_REASONS } from "@/pages/MentorshipAdminPrototype/mockData";

/** Room the recommendation reason has once published: `String(300)`. */
export const REASON_LIMIT = 300;

const scoreOf = (mentorId, menteeId) =>
  40 +
  ((mentorId * 7 + menteeId * 13) % 35) +
  (MATCH_REASONS[`${menteeId}-${mentorId}`] ? 30 : 0);

/**
 * A stand-in for the matcher, so the prototype has something to review.
 *
 * Deterministic on purpose: the same selection gives the same result. Each
 * mentor goes in with the slots they have left, not their cap, and a mentee
 * nobody could take still gets a row — those are the ones that most need a
 * person to look at them.
 *
 * @param {{mentors: Array<{userId: number, freeSlots: number}>, mentees: Array<{userId: number}>}} input
 * @returns {{rows: object[], unmatchedMentorIds: number[]}}
 */
export const simulateRun = ({ mentors, mentees }) => {
  const left = Object.fromEntries(mentors.map((m) => [m.userId, m.freeSlots]));
  const scored = mentees.flatMap((e) =>
    mentors.map((m) => ({
      menteeId: e.userId,
      mentorId: m.userId,
      score: scoreOf(m.userId, e.userId),
    })),
  );

  const chosen = {};
  [...scored]
    .sort((a, b) => b.score - a.score)
    .forEach(({ menteeId, mentorId, score }) => {
      if (chosen[menteeId] || left[mentorId] <= 0) return;
      chosen[menteeId] = { mentorId, score };
      left[mentorId] -= 1;
    });

  const rows = mentees.map((e) => {
    const pick = chosen[e.userId];
    const candidates = scored
      .filter((s) => s.menteeId === e.userId && s.mentorId !== pick?.mentorId)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map(({ mentorId, score }) => ({ mentorId, score }));
    return {
      menteeId: e.userId,
      mentorId: pick?.mentorId ?? null,
      matchType: pick ? "hungarian" : "unmatched",
      score: pick?.score ?? null,
      reason: pick
        ? (MATCH_REASONS[`${e.userId}-${pick.mentorId}`] ??
          "Overlapping skills and industry; availability fits.")
        : "",
      candidates,
    };
  });

  const used = new Set(rows.map((r) => r.mentorId).filter(Boolean));
  return {
    rows,
    unmatchedMentorIds: mentors
      .map((m) => m.userId)
      .filter((id) => !used.has(id)),
  };
};
