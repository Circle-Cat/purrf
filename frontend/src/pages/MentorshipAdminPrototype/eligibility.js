/**
 * Who can go into a matching run, as one rule used everywhere it is asked:
 * the Eligible filter, the Needs exemption count, and the re-check when a run
 * is published. Asking it in three places with three copies is how a person
 * leaves the pool on one screen and stays in it on another.
 */

/**
 * Statuses that can go into a run. `un_matched` is included: coming out of
 * one run without a partner does not rule someone out of the next.
 */
export const POOL_STATUSES = ["signed_up", "matched", "un_matched"];

/** A mentee always takes one mentor; a mentor takes up to their own cap. */
export const capacityOf = (person) =>
  person.role === "mentor" ? (person.maxPartners ?? 1) : 1;

/** Active pairs this person is in, in their own round. */
export const activePairsOf = (person, pairs) =>
  pairs.filter(
    (p) =>
      p.roundId === person.roundId &&
      p.status === "active" &&
      (p.mentorId === person.userId || p.menteeId === person.userId),
  );

export const freeSlotsOf = (person, pairs) =>
  capacityOf(person) - activePairsOf(person, pairs).length;

/**
 * The first thing keeping someone out of a run, or null when nothing does.
 *
 * Blocked and deactivated accounts never go in. Training has to be done —
 * there is no exemption for it. A past that needs looking at keeps someone out
 * until an exemption is approved for this round, and an exemption stands in
 * for that and nothing else.
 *
 * @returns {null|"blocked"|"deactivated"|"training"|"status"|"full"|"history"}
 */
export const matchingBlocker = (
  person,
  { pairs, account, exempt, historyIssues },
) => {
  if (account.isBlocked) return "blocked";
  if (!account.isActive) return "deactivated";
  if (!POOL_STATUSES.includes(person.approvalStatus)) return "status";
  if (!person.onboardingDone) return "training";
  if (freeSlotsOf(person, pairs) <= 0) return "full";
  if (historyIssues.length > 0 && !exempt) return "history";
  return null;
};

/** Why a person given a place in a run can no longer take it, in words. */
export const BLOCKER_TEXT = {
  blocked: "is blocked",
  deactivated: "is deactivated",
  status: "has withdrawn or been closed out",
  training: "has not finished training",
  full: "has no free slot left",
  history: "needs an exemption first",
};
