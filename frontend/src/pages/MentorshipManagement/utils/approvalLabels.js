import { ROUTE_PATHS } from "@/constants/RoutePaths";

/** The mentorship approval actions, as the API names them. */
export const APPROVAL_ACTION = Object.freeze({
  PUBLISH_MATCHING: "publish_matching",
  EXEMPT_MATCHING: "exempt_matching",
});

const ACTION_LABELS = {
  [APPROVAL_ACTION.PUBLISH_MATCHING]: "Publish matching result",
  [APPROVAL_ACTION.EXEMPT_MATCHING]: "Matching exemption",
};

/**
 * What a mentorship approval request asks for, as a short label.
 * @param {string} action - The request's action.
 * @returns {string}
 */
export const approvalActionLabel = (action) =>
  ACTION_LABELS[action] ?? "Approval";

/**
 * Where a reviewer decides a request: decisions are taken on the page of the
 * thing they are about. A publish request opens that round's matching
 * results; an exemption opens the round's Needs exemption list narrowed to
 * the person.
 *
 * @param {{action: string, round: {roundId: number},
 *          person?: {userId: number}|null}} request
 * @returns {{pathname: string, search: string}}
 */
export const approvalReviewLink = (request) => {
  const roundId = request.round?.roundId;
  if (request.action === APPROVAL_ACTION.EXEMPT_MATCHING) {
    const search = new URLSearchParams({
      round: String(roundId),
      needsExemption: "1",
    });
    if (request.person?.userId != null) {
      search.set("id", String(request.person.userId));
    }
    return {
      pathname: ROUTE_PATHS.MENTORSHIP_MANAGEMENT,
      search: `?${search.toString()}`,
    };
  }
  return { pathname: ROUTE_PATHS.MENTORSHIP_MATCHING(roundId), search: "" };
};

/**
 * A person on a request, by name or, when the name did not resolve, by id.
 * @param {{userId: number|string, name?: string|null}|null|undefined} person
 * @returns {string}
 */
export const approvalPersonLabel = (person) => {
  if (!person) return "";
  return person.name || `ID ${person.userId}`;
};
