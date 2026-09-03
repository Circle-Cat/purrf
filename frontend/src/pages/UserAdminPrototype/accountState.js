import {
  ACTOR_NAMES,
  BLOCK_IMPACT,
  EMPTY_IMPACT,
} from "@/pages/UserAdminPrototype/mockData";

/** "Zhao, Min" — the console lists colleagues and candidates the same way. */
export const fullName = (user) => `${user.firstName}, ${user.lastName}`;

/** Actor ids never reach the screen; an unknown one is still not a number. */
export const actorName = (userId) =>
  userId == null ? "—" : (ACTOR_NAMES[userId] ?? `User ${userId}`);

/** What a block would sweep. Absent means nothing to sweep, not unknown. */
export const impactFor = (userId) => BLOCK_IMPACT[userId] ?? EMPTY_IMPACT;

/**
 * Every state a row can be in, in the order they are shown.
 *
 * Blocked and deactivated are orthogonal flags, so a row can carry both and
 * the list has to render both. A pending block request is a third, separate
 * marker: the target is still fully active while a request waits.
 *
 * @param {object} user
 * @param {boolean} hasPendingRequest
 * @returns {string[]}
 */
export const statesOf = (user, hasPendingRequest) => {
  const states = [];
  if (user.isBlocked) states.push("blocked");
  if (!user.isActive) states.push("deactivated");
  if (hasPendingRequest) states.push("requested");
  if (states.length === 0) states.push("active");
  return states;
};
