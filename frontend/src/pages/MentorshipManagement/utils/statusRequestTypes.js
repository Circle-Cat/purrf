import {
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

const MARK_CONSEQUENCES =
  "Recorded on their history. It keeps them out of matching until an exemption, including later in this round. It cannot be undone. They are not told.";

/**
 * What the detail page's "Change status / flag" dialog can ask for, one entry
 * per kind of request. `isAvailable` says whether it can be asked for now;
 * `pair` says whether it names one of the person's pairs this round; `raise`
 * sends it; `consequences` is what approving it does, shown before sending
 * and again to the reviewer.
 */
export const STATUS_REQUEST_TYPES = Object.freeze([
  {
    key: APPROVAL_ACTION.WITHDRAW_PARTICIPANT,
    label: "Withdraw from round",
    pair: PAIR_RULE.NONE,
    consequences: (name) =>
      `${name} leaves this round: every pair they have in it ends, and their meetings that have not started are cancelled. Their partners stay matched. This cannot be undone.`,
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
]);

/**
 * The request types that can be asked for right now: those that apply and
 * are not already waiting on a decision for this person.
 * @param {{canWrite: boolean, round: Object, registration: Object|null, pendingRequests?: {action: string}[]}} context
 * @returns {Object[]}
 */
export const availableStatusRequestTypes = (context) => {
  const waiting = new Set(
    (context.pendingRequests ?? []).map((request) => request.action),
  );
  return STATUS_REQUEST_TYPES.filter(
    (type) => !waiting.has(type.key) && type.isAvailable(context),
  );
};

/**
 * The request type for an approval action, or null for one not raised here.
 * @param {string} action
 * @returns {Object|null}
 */
export const statusRequestType = (action) =>
  STATUS_REQUEST_TYPES.find((type) => type.key === action) ?? null;
