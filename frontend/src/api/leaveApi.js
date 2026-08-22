import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * Fetches every leave request ever filed against the signed-in user.
 *
 * Decided requests included, deliberately. Nobody carries a manager flag --
 * approving is not a permission, and a manager who gets no leave themselves
 * has no employment profile to read it off -- so an empty list is the only
 * thing that says somebody approves for nobody. Asking for pending alone
 * would make the approvals entry point vanish the moment a manager finished
 * deciding.
 *
 * @returns {Promise<object>} The API envelope; `data` is the request list,
 *   oldest first.
 */
export async function getLeaveApprovals() {
  return await request.get(API_ENDPOINTS.LEAVE_APPROVALS);
}

/**
 * Approves or rejects one request filed against the signed-in user.
 *
 * The server checks that the caller is the approver the request was filed
 * against, so a decision that is not yours fails there rather than here.
 *
 * @param {number} requestId - The request being decided.
 * @param {boolean} approve - True to approve, false to reject.
 * @returns {Promise<object>} The API envelope; `data` is the decided request.
 */
export async function decideLeaveRequest(requestId, approve) {
  return await request.post(API_ENDPOINTS.LEAVE_REQUEST_DECISION(requestId), {
    approve,
  });
}
