import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * Fetch all mentorship rounds.
 */
export const getAllMentorshipRounds = () =>
  request.get(API_ENDPOINTS.MENTORSHIP_ROUNDS);

/**
 * Fetch the mentorship partners for a specific round.
 * @param {string} roundId - Optional: the ID of the mentorship round.
 */
export const getMyMentorshipPartners = (roundId) =>
  request.get(API_ENDPOINTS.MENTORSHIP_PARTNERS, {
    params: { roundId },
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
