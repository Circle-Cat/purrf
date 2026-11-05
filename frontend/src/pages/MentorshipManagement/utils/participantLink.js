import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * Where a person's detail page is for a round, optionally opened on a pair,
 * or opened to review one request about them.
 *
 * @param {number|string} userId
 * @param {number|string|null} roundId
 * @param {number|string|null} [pairId]
 * @param {number|string|null} [reviewRequestId] - Opens the page in review
 *   mode on this request.
 * @returns {{pathname: string, search: string}}
 */
export const participantLink = (
  userId,
  roundId,
  pairId = null,
  reviewRequestId = null,
) => {
  const search = new URLSearchParams();
  if (roundId != null && roundId !== "") search.set("round", String(roundId));
  if (pairId != null) search.set("pair", String(pairId));
  if (reviewRequestId != null) search.set("review", String(reviewRequestId));
  const query = search.toString();
  return {
    pathname: ROUTE_PATHS.MENTORSHIP_PARTICIPANT(userId),
    search: query ? `?${query}` : "",
  };
};
