import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * Paginated account list with optional search and state filters.
 * @param {{search?: string, userId?: number|string, status?: string,
 *          userType?: string, limit?: number, offset?: number}} params
 */
export const getAccounts = ({
  search,
  userId,
  status,
  userType,
  limit,
  offset,
} = {}) =>
  request.get(API_ENDPOINTS.ADMIN_ACCOUNTS, {
    params: {
      search,
      user_id: userId,
      status,
      user_type: userType,
      limit,
      offset,
    },
  });

/** How one account can sign in: its emails and its identity rows. */
export const getSignInMethods = (userId) =>
  request.get(API_ENDPOINTS.ADMIN_ACCOUNT_SIGN_IN_METHODS(userId));

/** Deactivate an account. The note is optional and kept with the record. */
export const deactivateAccount = (userId, note) =>
  request.post(API_ENDPOINTS.ADMIN_ACCOUNT_DEACTIVATE(userId), { note });

/** Undo a deactivation. */
export const reactivateAccount = (userId) =>
  request.post(API_ENDPOINTS.ADMIN_ACCOUNT_REACTIVATE(userId));

/** Lift a block. Restores access and nothing else. */
export const unblockAccount = (userId) =>
  request.post(API_ENDPOINTS.ADMIN_ACCOUNT_UNBLOCK(userId));

/** Block someone without going through a request. Reason is required. */
export const blockAccount = (userId, reason) =>
  request.post(API_ENDPOINTS.ADMIN_ACCOUNT_BLOCK(userId), { reason });

/** What blocking this person is about to do: counts and dates only. */
export const getBlockPreflight = (userId) =>
  request.get(API_ENDPOINTS.BLOCK_PREFLIGHT(userId));

/**
 * Ask a named reviewer to block someone.
 * @param {{userId: number, reason: string, reviewerId: number}} body
 * @param {string} raisedFrom Domain page the request came from. A query
 *   parameter on the wire, not a body field.
 */
export const createBlockRequest = (
  { userId, reason, reviewerId },
  raisedFrom,
) =>
  request.post(
    API_ENDPOINTS.BLOCK_REQUESTS,
    { userId, reason, reviewerId },
    { params: { raised_from: raisedFrom } },
  );

/** The requests waiting on the caller's own decision. Nobody else's. */
export const getPendingBlockRequests = () =>
  request.get(API_ENDPOINTS.BLOCK_REQUESTS);

/** Hand a request the caller raised to a different reviewer. */
export const reassignBlockRequest = (requestId, reviewerId) =>
  request.post(API_ENDPOINTS.BLOCK_REQUEST_REASSIGN(requestId), { reviewerId });

/** Approve or turn down a request the caller was named to decide. */
export const decideBlockRequest = (requestId, approved, note) =>
  request.post(API_ENDPOINTS.BLOCK_REQUEST_DECIDE(requestId), {
    approved,
    note,
  });

/** Pickable reviewers for a block request: id and name only. */
export const getUserAdmins = () =>
  request.get(API_ENDPOINTS.BLOCK_REQUEST_REVIEWERS);
