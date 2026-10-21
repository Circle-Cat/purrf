import { legalName } from "@/utils/userName";

/**
 * Render the actor of a grant or revocation, in the single cell a "By" column
 * has room for.
 *
 * A grant can outlive the account that made it, so an id with no resolved
 * person still shows the id rather than hiding it — losing "somebody did this"
 * is worse than showing a number. An em dash means there was no actor at all,
 * which is the case for a super-admin-derived row seeded without a marker.
 *
 * @param {object} [person] The resolved actor, when there is one.
 * @param {number|null} [userId] The raw id, used as the fallback.
 * @returns {string}
 */
export const actorLabel = (person, userId) => {
  const name = legalName(person);
  if (name) return name;
  return userId == null ? "—" : `User ${userId}`;
};
