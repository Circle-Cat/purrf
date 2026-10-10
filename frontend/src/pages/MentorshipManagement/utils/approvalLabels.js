import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { participantLink } from "@/pages/MentorshipManagement/utils/participantLink";

/** The mentorship approval actions, as the API names them. */
export const APPROVAL_ACTION = Object.freeze({
  PUBLISH_MATCHING: "publish_matching",
  EXEMPT_MATCHING: "exempt_matching",
  WITHDRAW_PARTICIPANT: "withdraw_participant",
  MARK_NO_SHOW: "mark_no_show",
  MARK_RED_FLAG: "mark_red_flag",
  END_PAIR: "end_pair",
});

const ACTION_LABELS = {
  [APPROVAL_ACTION.PUBLISH_MATCHING]: "Publish matching result",
  [APPROVAL_ACTION.EXEMPT_MATCHING]: "Matching exemption",
  [APPROVAL_ACTION.WITHDRAW_PARTICIPANT]: "Withdrawal from round",
  [APPROVAL_ACTION.MARK_NO_SHOW]: "No show mark",
  [APPROVAL_ACTION.MARK_RED_FLAG]: "Red flag",
  [APPROVAL_ACTION.END_PAIR]: "End pair",
};

// Requests about one person in one round, decided on their page.
const DECIDED_ON_PERSON_PAGE = new Set([
  APPROVAL_ACTION.WITHDRAW_PARTICIPANT,
  APPROVAL_ACTION.MARK_NO_SHOW,
  APPROVAL_ACTION.MARK_RED_FLAG,
]);

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
 * the person; a withdrawal or a mark opens the person's page for the round;
 * ending a pair opens the mentee's page.
 *
 * @param {{action: string, round: {roundId: number},
 *          person?: {userId: number}|null,
 *          pair?: {mentee: {userId: number}}|null}} request
 * @returns {{pathname: string, search: string}}
 */
export const approvalReviewLink = (request) => {
  const roundId = request.round?.roundId;
  if (request.action === APPROVAL_ACTION.END_PAIR) {
    return participantLink(request.pair?.mentee?.userId, roundId);
  }
  if (DECIDED_ON_PERSON_PAGE.has(request.action)) {
    return participantLink(request.person?.userId, roundId);
  }
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

/**
 * The two people in a pair a request is about, mentor first.
 * @param {{mentor: {userId: number|string, name?: string|null},
 *          mentee: {userId: number|string, name?: string|null}}|null|undefined} pair
 * @returns {string}
 */
export const approvalPairLabel = (pair) =>
  pair
    ? `mentor ${approvalPersonLabel(pair.mentor)} and mentee ${approvalPersonLabel(pair.mentee)}`
    : "";

/**
 * Why someone needs a matching exemption, one line per problem. A problem
 * from the round being looked at says "this round".
 * @param {{reason: string, roundId?: number|null, roundName?: string|null,
 *          completed?: number|null, required?: number|null}[]} findings
 * @param {number|string|null} [currentRoundId] The round being looked at.
 * @returns {string[]}
 */
export const exemptionWhyLines = (findings, currentRoundId = null) =>
  (findings ?? []).map((f) => {
    const round =
      currentRoundId != null && String(f.roundId) === String(currentRoundId)
        ? "this round"
        : f.roundName || "an earlier round";
    if (f.reason === "quit_after_match") {
      return `Quit after being matched in ${round}`;
    }
    if (f.reason === "meetings_short") {
      return `Meetings short in ${round}: ${f.completed ?? 0} of ${f.required ?? "?"}`;
    }
    if (f.reason === "no_show") return `No show in ${round}`;
    if (f.reason === "red_flag") return `Red flag in ${round}`;
    return f.reason;
  });
