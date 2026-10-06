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
