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

/**
 * Whether the leave feature applies to the signed-in account.
 *
 * "Not covered" and "covered with nothing yet" both look like an empty
 * ledger, so this is asked rather than inferred: showing somebody outside the
 * population a balance of zero reads as an entitlement of nothing rather than
 * as a feature with nothing to do with them.
 *
 * @returns {Promise<object>} The API envelope; `data.isCovered` is the answer.
 */
export async function getLeaveCoverage() {
  return await request.get(API_ENDPOINTS.LEAVE_ME);
}

/**
 * Fetches the signed-in employee's own requests, newest first.
 *
 * @returns {Promise<object>} The API envelope; `data` is the request list.
 */
export async function getMyLeaveRequests() {
  return await request.get(API_ENDPOINTS.LEAVE_REQUESTS);
}

/**
 * Files a leave, sick or exchange request for the signed-in employee.
 *
 * Times are only meaningful on a single day of leave: a range is always whole
 * days and an exchange is always whole days. Sending them anywhere else is
 * refused by the server rather than ignored, so the caller must leave them out.
 *
 * @param {{type: string, startDate: string, endDate: string,
 *          startTime: string|null, endTime: string|null,
 *          reason: string|null}} payload - The request being filed.
 * @returns {Promise<object>} The API envelope; `data` is the stored request.
 */
export async function submitLeaveRequest(payload) {
  return await request.post(API_ENDPOINTS.LEAVE_REQUESTS, payload);
}

/**
 * Takes back one of the signed-in employee's undecided requests.
 *
 * Only a pending request can be taken back. Approval is the end of the line:
 * putting the hours back afterwards is an admin adjustment with a note on it.
 *
 * @param {number} requestId - The request being withdrawn.
 * @returns {Promise<object>} The API envelope; `data` is the withdrawn request.
 */
export async function withdrawLeaveRequest(requestId) {
  return await request.post(API_ENDPOINTS.LEAVE_REQUEST_WITHDRAW(requestId));
}

/**
 * Fetches the read-only leave constants.
 *
 * @returns {Promise<object>} The API envelope; `data` is the policy.
 */
export async function getLeavePolicy() {
  return await request.get(API_ENDPOINTS.LEAVE_POLICY);
}

/**
 * Fetches one year of company holidays.
 *
 * A year nobody has entered answers with an empty list rather than a 404:
 * absent is a normal state for a year that has not been planned yet.
 *
 * @param {number} year - The calendar year.
 * @returns {Promise<object>} The API envelope; `data` is that year's holidays.
 */
export async function getLeaveHolidays(year) {
  return await request.get(API_ENDPOINTS.LEAVE_HOLIDAYS_YEAR(year));
}

/**
 * Fetches the years that have any company holidays entered.
 *
 * @returns {Promise<object>} The API envelope; `data` is the list of years.
 */
export async function getLeaveHolidayYears() {
  return await request.get(API_ENDPOINTS.LEAVE_HOLIDAY_YEARS);
}
