import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * Fetch all mentorship rounds.
 * @param {boolean} needDetails - Optional: include additional round details for mentorship admins.
 */
export const getAllMentorshipRounds = (needDetails = false) =>
  request.get(API_ENDPOINTS.MENTORSHIP_ROUNDS, {
    params: { need_details: needDetails },
  });

/**
 * Fetch which rounds the Personal Dashboard acts on right now: the
 * registration round and whether it is open, whether its matching result is
 * viewable, whether any round is in its feedback phase, and the default
 * round to show. Evaluated on the server's clock.
 */
export const getMentorshipRoundSlots = () =>
  request.get(API_ENDPOINTS.MENTORSHIP_ROUND_SLOTS);

/**
 * Create or update a mentorship round (admin only).
 * @param {object} data - Round form data to submit.
 */
export const upsertMentorshipRound = (data) =>
  request.post(API_ENDPOINTS.MENTORSHIP_ROUNDS, data);

/**
 * Fetch the mentorship partners for a specific round.
 * @param {string} roundId - Optional: the ID of the mentorship round.
 */
export const getMyMentorshipPartners = (roundId) =>
  request.get(API_ENDPOINTS.MENTORSHIP_PARTNERS, {
    params: { round_id: roundId },
  });

/**
 * Fetch the mentorship registration information for a specific round.
 * @param {string} roundId - The ID of the mentorship round.
 * @param {"mentor"|"mentee"} [role] - Which role's form to prefill. Omit to
 *   ask only whether the user is registered and under what role.
 */
export const getMyMentorshipRegistration = (roundId, role) =>
  request.get(API_ENDPOINTS.MENTORSHIP_REGISTRATION(roundId), {
    params: role ? { role } : undefined,
  });

/**
 * Fetch the mentorship match result for a specific round.
 * @param {string} roundId - The ID of the mentorship round.
 */
export const getMyMentorshipMatchResult = (roundId) =>
  request.get(API_ENDPOINTS.MENTORSHIP_MATCH_RESULT(roundId));

/**
 * Register for a specific mentorship round with the provided data.
 * @param {string} roundId - The ID of the mentorship round.
 * @param {object} data - The registration data.
 */
export const postMyMentorshipRegistration = (roundId, data) =>
  request.post(API_ENDPOINTS.MENTORSHIP_REGISTRATION(roundId), data);

/** Fetch the mentorship meeting log for a specific round
 * @param {string} roundId - The ID of the mentorship round.
 */
export const getMyMentorshipMeetingLog = (roundId) =>
  request.get(API_ENDPOINTS.MENTORSHIP_MEETINGS_ENDPOINT, {
    params: { round_id: roundId },
  });

/** Submit the mentorship meeting log for a specific round
 * @param {object} data - The meeting log data. Must carry `partnerId` alongside
 *   `roundId`: the round alone does not identify a pair, since a participant can
 *   hold more than one pair in the same round.
 */
export const postMyMentorshipMeetingLog = (data) =>
  request.post(API_ENDPOINTS.MENTORSHIP_MEETINGS_ENDPOINT, data);

/**
 * Fetch the current user's program feedback for a specific round.
 * @param {string} roundId - The ID of the mentorship round.
 */
export const getMyMentorshipFeedback = (roundId) =>
  request.get(API_ENDPOINTS.MENTORSHIP_FEEDBACK(roundId));

/**
 * Submit or overwrite program feedback for a specific round.
 * @param {string} roundId - The ID of the mentorship round.
 * @param {object} data - The feedback payload.
 */
export const postMyMentorshipFeedback = (roundId, data) =>
  request.post(API_ENDPOINTS.MENTORSHIP_FEEDBACK(roundId), data);

/**
 * Admin participant search across registered participants.
 *
 * Filter params are sent camelCase, not snake_case like this file's other GET
 * params — the backend binds this endpoint's filters via a Pydantic model
 * (`Depends()`) that only recognizes its camelCase aliases.
 *
 * @param {{userId?: number, q?: string,
 *          accountStatus?: "active"|"blocked"|"deactivated",
 *          internal?: "internal"|"external",
 *          roundId?: number, participantRole?: string, approvalStatus?: string,
 *          onboardingStatus?: string, eligible?: boolean,
 *          limit?: number, offset?: number, sortBy?: string, order?: "asc"|"desc"}} filters
 *
 * `q` matches name parts and any of the person's email addresses. `eligible`
 * keeps the people eligible for matching in the round, which must be in
 * progress.
 *
 * sortBy/order are sent as sort_by/order because, unlike the other filters,
 * they are plain query parameters on the endpoint rather than fields on its
 * camelCase-aliased filter model.
 */
export const searchParticipants = ({
  userId,
  q,
  accountStatus,
  internal,
  roundId,
  participantRole,
  approvalStatus,
  onboardingStatus,
  eligible,
  needsExemption,
  limit,
  offset,
  sortBy,
  order,
} = {}) =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_PARTICIPANTS, {
    params: {
      userId,
      q,
      accountStatus,
      internal,
      roundId,
      participantRole,
      approvalStatus,
      onboardingStatus,
      eligible,
      needsExemption,
      limit,
      offset,
      sort_by: sortBy,
      order,
    },
  });

/**
 * People admitted as a mentor or mentee who have not registered for a round,
 * one row per person by user ID.
 *
 * Filters go camelCase, as for searchParticipants; `order` is a plain query
 * parameter. `admittedRole` keeps only those admitted as that role.
 *
 * @param {number|string} roundId
 * @param {{userId?: number, q?: string,
 *          accountStatus?: "active"|"blocked"|"deactivated",
 *          internal?: "internal"|"external", admittedRole?: "mentor"|"mentee",
 *          limit?: number, offset?: number, order?: "asc"|"desc"}} filters
 */
export const searchUnregistered = (
  roundId,
  {
    userId,
    q,
    accountStatus,
    internal,
    admittedRole,
    limit,
    offset,
    order,
  } = {},
) =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_ROUND_UNREGISTERED(roundId), {
    params: {
      userId,
      q,
      accountStatus,
      internal,
      admittedRole,
      limit,
      offset,
      order,
    },
  });

/**
 * Fetch a round's feedback for the admin console: everyone it is asked of,
 * sent or not, with what each of them wrote.
 * @param {number} roundId - The mentorship round's id.
 */
export const getRoundFeedback = (roundId) =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_ROUND_FEEDBACK(roundId));

/**
 * Start a matching run for a round over the chosen participants (admin only).
 * Resolves to `data: { runId }`.
 * @param {{roundId: number, participantIds: number[]}} body
 */
export const startMatchingRun = ({ roundId, participantIds }) =>
  request.post(API_ENDPOINTS.MENTORSHIP_ADMIN_MATCH_RUNS, {
    roundId,
    participantIds,
  });

/**
 * Fetch where a round's latest matching run stands.
 * @param {number|string} roundId
 */
export const getMatchingRun = (roundId) =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_MATCH_RUN(roundId));

/**
 * Fetch a page of a round's latest matching results, one item per mentee.
 * @param {number|string} roundId
 * @param {{limit?: number, offset?: number, matched?: boolean}} filters -
 *   `matched` keeps only matched (true) or unmatched (false) mentees; leave it
 *   out for all.
 */
export const getMatchingResults = (roundId, { limit, offset, matched } = {}) =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_MATCH_RUN_RESULTS(roundId), {
    params: { limit, offset, matched },
  });

/**
 * Fetch a page of the people a round's latest matching left without a
 * partner, one item per person, mentees first then mentors.
 * @param {number|string} roundId
 * @param {{limit?: number, offset?: number}} page
 */
export const getMatchingUnmatched = (roundId, { limit, offset } = {}) =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_MATCH_RUN_UNMATCHED(roundId), {
    params: { limit, offset },
  });

/**
 * Take the lock on editing a round's matching result, or renew it when it is
 * already mine. Resolves to `data: { userId, name, expiresAt }`; refused with
 * 409 while someone else holds it.
 * @param {number|string} roundId
 */
export const takeMatchingEditLock = (roundId) =>
  request.post(API_ENDPOINTS.MENTORSHIP_ADMIN_MATCH_RUN_EDIT_LOCK(roundId));

/**
 * Give up my lock on editing a round's matching result; nothing happens when
 * it is not mine.
 * @param {number|string} roundId
 */
export const releaseMatchingEditLock = (roundId) =>
  request.delete(API_ENDPOINTS.MENTORSHIP_ADMIN_MATCH_RUN_EDIT_LOCK(roundId));

/**
 * The same release for a page that is going away. An XHR in flight when the
 * tab closes is dropped; fetch with keepalive survives it, so this one goes
 * around axios. Best effort: a failure is only logged.
 * @param {number|string} roundId
 */
export const releaseMatchingEditLockOnLeave = (roundId) =>
  fetch(
    `${request.defaults.baseURL}${API_ENDPOINTS.MENTORSHIP_ADMIN_MATCH_RUN_EDIT_LOCK(roundId)}`,
    { method: "DELETE", keepalive: true, credentials: "include" },
  ).catch((error) => {
    console.error("Failed to release the matching edit lock", error);
  });

/**
 * Save changed mentees into a round's matching draft. Needs my edit lock and
 * releases it. A change equal to the matcher's result takes that mentee out
 * of the draft. Resolves to `data: { draftCount }`.
 * @param {number|string} roundId
 * @param {{menteeId: string, mentorId: string|null,
 *          recommendationReason: string}[]} changes
 */
export const saveMatchingDraft = (roundId, changes) =>
  request.patch(API_ENDPOINTS.MENTORSHIP_ADMIN_MATCH_RUN_DRAFT(roundId), {
    changes,
  });

/**
 * Fetch the mentorship admin view of a pair's meeting log for the round.
 * @param {number} pairId - The mentorship pair's id.
 */
export const getMeetingLog = (pairId) =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_PAIR_MEETINGS(pairId));

/**
 * Apply batch updates and deletes to a pair's v2 meeting log entries.
 * @param {number} pairId - The mentorship pair's id.
 * @param {{
 *   updates: Array<{meetingId: string, isCompleted?: boolean, note?: string[]}>,
 *   deletes: string[],
 * }} body - Only the fields present on an update entry are changed; omit a
 *   field to leave it untouched rather than sending its current value.
 */
export const updateMeetingLog = (pairId, body) =>
  request.patch(API_ENDPOINTS.MENTORSHIP_ADMIN_PAIR_MEETINGS(pairId), body);

/**
 * Ask a named reviewer to approve publishing a round's latest matching
 * result. Resolves to `data` = the new approval request; refused with 409
 * when the result cannot be published now or is already waiting.
 * @param {number|string} roundId
 * @param {{reviewerId: number, reason: string}} body
 */
export const requestMatchingPublish = (roundId, { reviewerId, reason }) =>
  request.post(
    API_ENDPOINTS.MENTORSHIP_ADMIN_MATCH_RUN_PUBLISH_REQUEST(roundId),
    {
      reviewerId,
      reason,
    },
  );

/**
 * Fetch who a mentorship approval request can be sent to, me excepted.
 * Resolves to `data: [{ userId, name }]`.
 */
export const getMentorshipApprovers = () =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_APPROVERS);

/**
 * Fetch the mentorship approval requests waiting on my decision, oldest
 * first. Resolves to `data` = a list of approval requests.
 */
export const getMyMentorshipApprovals = () =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_APPROVALS_MINE);

/**
 * Hand a pending mentorship approval request I raised to another reviewer.
 * @param {number} requestId
 * @param {number} reviewerId
 */
export const reassignMentorshipApproval = (requestId, reviewerId) =>
  request.post(API_ENDPOINTS.MENTORSHIP_ADMIN_APPROVAL_REASSIGN(requestId), {
    reviewerId,
  });

/**
 * Approve or reject a mentorship approval request naming me. A rejection
 * needs a comment. An approval whose checks no longer hold is refused with
 * 409 and the reasons as its message; the request stays pending.
 * @param {number} requestId
 * @param {{decision: "approve"|"reject", comment?: string}} body
 */
export const decideMentorshipApproval = (requestId, { decision, comment }) =>
  request.post(API_ENDPOINTS.MENTORSHIP_ADMIN_APPROVAL_DECIDE(requestId), {
    decision,
    comment,
  });

/**
 * Take back a pending mentorship approval request I raised.
 * @param {number} requestId
 */
export const withdrawMentorshipApproval = (requestId) =>
  request.post(API_ENDPOINTS.MENTORSHIP_ADMIN_APPROVAL_WITHDRAW(requestId));

/**
 * Ask a named reviewer to exempt a person from the matching history check in
 * a round in progress. Resolves to `data` = the new approval request; refused
 * with 409 when the person does not need one or one is already waiting.
 * @param {number|string} roundId
 * @param {number} userId
 * @param {{reviewerId: number, reason: string}} body
 */
export const requestMatchingExemption = (
  roundId,
  userId,
  { reviewerId, reason },
) =>
  request.post(
    API_ENDPOINTS.MENTORSHIP_ADMIN_EXEMPTION_REQUEST(roundId, userId),
    { reviewerId, reason },
  );
