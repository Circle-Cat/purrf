import {
  requestParticipantEndPair,
  requestParticipantMark,
  requestParticipantWithdrawal,
} from "@/api/mentorshipApi";
import { MentorshipApprovalStatus } from "@/constants/MentorshipApprovalStatus";
import { APPROVAL_ACTION } from "@/pages/MentorshipManagement/utils/approvalLabels";

const STILL_IN_ROUND = new Set([
  MentorshipApprovalStatus.SIGNED_UP,
  MentorshipApprovalStatus.MATCHED,
  MentorshipApprovalStatus.UN_MATCHED,
]);

/** Whether a request type is about one of the person's pairs this round. */
export const PAIR_RULE = Object.freeze({
  NONE: "none",
  REQUIRED: "required",
  OPTIONAL: "optional",
});

/**
 * Whether one of the person's pairs is still going.
 * @param {{partner?: {isActive?: boolean}}|null|undefined} pair
 * @returns {boolean}
 */
export const isActivePair = (pair) => pair?.partner?.isActive !== false;

const MARK_CONSEQUENCES =
  "Recorded on their history. It keeps them out of matching until an exemption, including later in this round. It cannot be undone. They are not told.";

/**
 * What the detail page's "Change status / flag" dialog can ask for, one entry
 * per kind of request. `isAvailable` says whether it can be asked for now;
 * `pair` says whether it names one of the person's pairs this round; `raise`
 * sends it; `consequences` is what approving it does, shown before sending
 * and again to the reviewer. `pairChoices` narrows the pairs it can be about;
 * `partnerMayNotReview` keeps the chosen pair's partner off the reviewer list.
 */
export const STATUS_REQUEST_TYPES = Object.freeze([
  {
    key: APPROVAL_ACTION.WITHDRAW_PARTICIPANT,
    label: "Withdraw from round",
    pair: PAIR_RULE.NONE,
    consequences: (name) =>
      `${name} leaves this round: every pair they have in it ends, and their meetings that have not started are cancelled. A partner left with no other pair becomes unmatched. This cannot be undone.`,
    isAvailable: ({ canWrite, round, registration }) =>
      Boolean(
        canWrite &&
        round?.inProgress &&
        STILL_IN_ROUND.has(registration?.approvalStatus),
      ),
    raise: (roundId, userId, { reviewerId, reason }) =>
      requestParticipantWithdrawal(roundId, userId, { reviewerId, reason }),
  },
  {
    key: APPROVAL_ACTION.MARK_NO_SHOW,
    label: "Mark as no show",
    pair: PAIR_RULE.REQUIRED,
    consequences: () => MARK_CONSEQUENCES,
    isAvailable: ({ canWrite, round, registration }) =>
      Boolean(canWrite && round?.inProgress && registration?.pairs?.length > 0),
    raise: (roundId, userId, { reviewerId, reason, pairId }) =>
      requestParticipantMark(roundId, userId, {
        tag: "no_show",
        pairId,
        reviewerId,
        reason,
      }),
  },
  {
    key: APPROVAL_ACTION.MARK_RED_FLAG,
    label: "Raise a red flag",
    pair: PAIR_RULE.OPTIONAL,
    consequences: () => MARK_CONSEQUENCES,
    isAvailable: ({ canWrite, round, registration }) =>
      Boolean(canWrite && round?.inProgress && registration),
    raise: (roundId, userId, { reviewerId, reason, pairId = null }) =>
      requestParticipantMark(roundId, userId, {
        tag: "red_flag",
        pairId,
        reviewerId,
        reason,
      }),
  },
  {
    key: APPROVAL_ACTION.END_PAIR,
    label: "End this pair",
    pair: PAIR_RULE.REQUIRED,
    partnerMayNotReview: true,
    reviewerHint: () => "Neither person in the pair can review it.",
    pairChoices: (pairs, pendingRequests = []) => {
      const waiting = new Set(
        pendingRequests
          .filter((r) => r.action === APPROVAL_ACTION.END_PAIR)
          .map((r) => r.pairId),
      );
      return (pairs ?? []).filter(
        (pair) => isActivePair(pair) && !waiting.has(pair.pairId),
      );
    },
    consequences: (_name, { partnerName } = {}) =>
      `${partnerName ? `The pair with ${partnerName} ends` : "The pair you pick ends"} and its meetings that have not started are cancelled. Whoever has no other pair left becomes unmatched; both can be paired with someone else; these two cannot be paired again this round. This cannot be undone. Neither of them is told.`,
    isAvailable: ({ canWrite, round, registration, pendingRequests }) =>
      Boolean(
        canWrite &&
        round?.inProgress &&
        STILL_IN_ROUND.has(registration?.approvalStatus) &&
        statusRequestType(APPROVAL_ACTION.END_PAIR).pairChoices(
          registration?.pairs,
          pendingRequests,
        ).length > 0,
      ),
    raise: (roundId, userId, { reviewerId, reason, pairId }) =>
      requestParticipantEndPair(roundId, userId, {
        pairId,
        reviewerId,
        reason,
      }),
  },
]);

/**
 * The request types that can be asked for right now: those that apply and
 * are not already waiting on a decision for this person; a type about
 * one pair is offered while some pair has none waiting.
 * @param {{canWrite: boolean, round: Object, registration: Object|null, pendingRequests?: {action: string}[]}} context
 * @returns {Object[]}
 */
export const availableStatusRequestTypes = (context) => {
  const waiting = new Set(
    (context.pendingRequests ?? []).map((request) => request.action),
  );
  return STATUS_REQUEST_TYPES.filter(
    (type) =>
      (type.pairChoices || !waiting.has(type.key)) && type.isAvailable(context),
  );
};

/**
 * The request type for an approval action, or null for one not raised here.
 * @param {string} action
 * @returns {Object|null}
 */
export const statusRequestType = (action) =>
  STATUS_REQUEST_TYPES.find((type) => type.key === action) ?? null;
