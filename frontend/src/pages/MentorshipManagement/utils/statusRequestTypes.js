import { requestParticipantWithdrawal } from "@/api/mentorshipApi";
import { MentorshipApprovalStatus } from "@/constants/MentorshipApprovalStatus";
import { APPROVAL_ACTION } from "@/pages/MentorshipManagement/utils/approvalLabels";

const STILL_IN_ROUND = new Set([
  MentorshipApprovalStatus.SIGNED_UP,
  MentorshipApprovalStatus.MATCHED,
  MentorshipApprovalStatus.UN_MATCHED,
]);

/**
 * What the detail page's "Change status / flag" dialog can ask for, one entry
 * per kind of request. `isAvailable` says whether it can be asked for now;
 * `raise` sends it; `consequences` is what approving it does, shown before
 * sending and again to the reviewer.
 */
export const STATUS_REQUEST_TYPES = Object.freeze([
  {
    key: APPROVAL_ACTION.WITHDRAW_PARTICIPANT,
    label: "Withdraw from round",
    consequences: (name) =>
      `${name} leaves this round: every pair they have in it ends, and their meetings that have not started are cancelled. Their partners stay matched. This cannot be undone.`,
    isAvailable: ({ canWrite, round, registration }) =>
      Boolean(
        canWrite &&
          round?.inProgress &&
          STILL_IN_ROUND.has(registration?.approvalStatus),
      ),
    raise: (roundId, userId, body) =>
      requestParticipantWithdrawal(roundId, userId, body),
  },
]);

/**
 * The request types that can be asked for right now.
 * @param {{canWrite: boolean, round: Object, registration: Object|null}} context
 * @returns {Object[]}
 */
export const availableStatusRequestTypes = (context) =>
  STATUS_REQUEST_TYPES.filter((type) => type.isAvailable(context));

/**
 * The request type for an approval action, or null for one not raised here.
 * @param {string} action
 * @returns {Object|null}
 */
export const statusRequestType = (action) =>
  STATUS_REQUEST_TYPES.find((type) => type.key === action) ?? null;
