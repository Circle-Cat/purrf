import {
  personWithId,
  scoreLabel,
} from "@/pages/MentorshipManagement/utils/matchingLabels";

/** The longest reason the pair may be shown, in characters. */
export const REASON_LIMIT = 300;

/** The mentor select's value for "No mentor this round". */
export const NO_MENTOR = "none";

const idOf = (userId) => (userId == null ? null : String(userId));

/**
 * What the saved draft says for one mentee, from a Matched item or an
 * Unmatched mentee item.
 *
 * @param {Object} item
 * @returns {{menteeId: string, mentorId: string|null,
 *            recommendationReason: string}}
 */
export const savedRow = (item) => ({
  menteeId: String((item.mentee ?? item.person).userId),
  mentorId: idOf(item.mentor?.userId),
  recommendationReason: item.recommendationReason ?? "",
});

/**
 * What a mentee's row shows: the unsaved change when there is one, else the
 * saved draft.
 *
 * @param {Object} item
 * @param {Object<string, {mentorId: string|null,
 *                         recommendationReason: string}>} changes
 */
export const shownRow = (item, changes) => {
  const saved = savedRow(item);
  const change = changes[saved.menteeId];
  return change ? { ...saved, ...change } : saved;
};

/**
 * Whether a row's mentor or reason is not what the matcher proposed.
 *
 * @param {{mentorId: string|null, recommendationReason: string}} shown
 * @param {Object} item
 * @returns {boolean}
 */
export const differsFromMatcher = (shown, item) =>
  shown.mentorId !== idOf(item.matcherMentor?.userId) ||
  shown.recommendationReason !== (item.matcherReason ?? "");

/**
 * The mentors a mentee can be given: the matcher's, the saved one and every
 * candidate, each once, with the candidate score when there is one.
 *
 * @param {Object} item
 * @returns {{userId: string, name: string|null, score: number|null}[]}
 */
export const mentorChoices = (item) => {
  const scores = new Map(
    (item.candidates ?? []).map((c) => [String(c.userId), c.score ?? null]),
  );
  const seen = new Map();
  for (const person of [
    item.matcherMentor,
    item.mentor,
    ...(item.candidates ?? []),
  ]) {
    if (!person) continue;
    const userId = String(person.userId);
    if (seen.has(userId)) continue;
    seen.set(userId, {
      userId,
      name: person.name ?? null,
      score: scores.get(userId) ?? null,
    });
  }
  return [...seen.values()];
};

/**
 * Each mentor's slots and how many mentees they have once the unsaved changes
 * are counted: a mentee moved from A to B is one less for A, one more for B.
 *
 * @param {{userId: number|string, name: string|null, slots: number,
 *          assigned: number}[]} mentorSlots
 * @param {Object<string, {mentorId: string|null,
 *                         baseMentorId: string|null}>} changes
 * @returns {Map<string, {name: string|null, slots: number, assigned: number}>}
 */
export const slotsWithChanges = (mentorSlots, changes) => {
  const slots = new Map(
    (mentorSlots ?? []).map((m) => [
      String(m.userId),
      { name: m.name ?? null, slots: m.slots, assigned: m.assigned },
    ]),
  );
  const shift = (mentorId, by) => {
    const slot = mentorId == null ? null : slots.get(mentorId);
    if (slot) slot.assigned += by;
  };
  for (const change of Object.values(changes)) {
    if (change.mentorId === change.baseMentorId) continue;
    shift(change.baseMentorId, -1);
    shift(change.mentorId, 1);
  }
  return slots;
};

/**
 * "Ann Lee (ID 101) — 1 of 2 slots free · 0.87"; the slots are left out when
 * the run does not list the mentor, the score when there is none.
 *
 * @param {{userId: string, name: string|null, score: number|null}} choice
 * @param {{slots: number, assigned: number}|undefined} slot
 * @returns {string}
 */
export const mentorOptionLabel = (choice, slot) => {
  const free = slot
    ? ` — ${slot.slots - slot.assigned} of ${slot.slots} slots free`
    : "";
  const score = choice.score != null ? ` · ${scoreLabel(choice.score)}` : "";
  return `${personWithId(choice)}${free}${score}`;
};

const count = (n, noun) => `${n} ${noun}${n === 1 ? "" : "s"}`;

/**
 * One line for a problem the saved draft has, as the overview lists them. A
 * code this page does not know is shown as is.
 *
 * @param {Object} problem
 * @returns {string}
 */
export const problemText = (problem) => {
  switch (problem.code) {
    case "over_slots":
      return `${personWithId(problem.mentor)} is given ${count(problem.assigned, "mentee")} but has ${count(problem.slots, "slot")} this run.`;
    case "reason_too_long":
      return `The reason for ${personWithId(problem.mentee)} is over ${REASON_LIMIT} characters.`;
    case "no_reason":
      return `${personWithId(problem.mentee)} is matched with no reason.`;
    default:
      return problem.code;
  }
};
