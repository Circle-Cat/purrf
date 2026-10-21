import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * Where a person's detail page is for a round, optionally opened on a pair.
 *
 * @param {number|string} userId
 * @param {number|string|null} roundId
 * @param {number|string|null} [pairId]
 * @returns {{pathname: string, search: string}}
 */
export const participantLink = (userId, roundId, pairId = null) => {
  const search = new URLSearchParams();
  if (roundId != null && roundId !== "") search.set("round", String(roundId));
  if (pairId != null) search.set("pair", String(pairId));
  const query = search.toString();
  return {
    pathname: ROUTE_PATHS.MENTORSHIP_PARTICIPANT(userId),
    search: query ? `?${query}` : "",
  };
};
