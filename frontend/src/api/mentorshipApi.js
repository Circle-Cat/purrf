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
 */
export const getMyMentorshipRegistration = (roundId) =>
  request.get(API_ENDPOINTS.MENTORSHIP_REGISTRATION(roundId));

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
 * @param {object} data - The meeting log data
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
 * Admin participant search across a round's participants and non-participants.
 *
 * Filter params are sent camelCase, not snake_case like this file's other GET
 * params — the backend binds this endpoint's filters via a Pydantic model
 * (`Depends()`) that only recognizes its camelCase aliases.
 *
 * @param {{userId?: number, name?: string, email?: string, matchedUser?: string,
 *          roundId?: number, participantRole?: string, approvalStatus?: string,
 *          onboardingStatus?: string, participationStatus?: "participant"|"non_participant",
 *          limit?: number, offset?: number, sortBy?: string, order?: "asc"|"desc"}} filters
 *
 * sortBy/order are sent as sort_by/order because, unlike the other filters,
 * they are plain query parameters on the endpoint rather than fields on its
 * camelCase-aliased filter model.
 */
export const searchParticipants = ({
  userId,
  name,
  email,
  matchedUser,
  roundId,
  participantRole,
  approvalStatus,
  onboardingStatus,
  participationStatus,
  limit,
  offset,
  sortBy,
  order,
} = {}) =>
  request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_PARTICIPANTS, {
    params: {
      userId,
      name,
      email,
      matchedUser,
      roundId,
      participantRole,
      approvalStatus,
      onboardingStatus,
      participationStatus,
      limit,
      offset,
      sort_by: sortBy,
      order,
    },
  });
