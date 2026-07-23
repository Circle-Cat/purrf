import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * Delete a single meeting. (Called when the user selects only one meeting on the frontend)
 * @param {string|number} meetingId - The unique identifier of the meeting
 * @param {number} roundId - The current mentorship round ID (required for backend DTO validation)
 * @param {number} partnerId - The ID of the partner (required for backend DTO validation)
 */
export const deleteMeeting = (meetingId, roundId, partnerId) => {
  return request.delete(API_ENDPOINTS.MENTORSHIP_MEETING_V2_SINGLE(meetingId), {
    params: {
      round_id: roundId,
      partner_id: partnerId,
    },
  });
};

/**
 * Batch delete multiple meetings. (Called when the user selects multiple meetings on the frontend)
 * @param {Array<{round_id: number, partner_id: number, meeting_ids: string[]}>} deletions - The deletion payload grouped by (round_id, partner_id)
 */
export const batchDeleteMeetings = (deletions) => {
  return request.post(API_ENDPOINTS.MENTORSHIP_MEETING_V2_BATCH_DELETE, {
    deletions,
  });
};

/**
 * Get my meetings for a specific round.
 * @param {string|number} roundId - The current mentorship round ID
 */
export const getMyMentorshipMeetingsV2 = ({ roundId, includeDetails }) =>
  request.get(API_ENDPOINTS.MENTORSHIP_MEETINGS_V2, {
    params: {
      round_id: roundId,
      include_details: includeDetails,
    },
  });

/**
 * Create a mentorship meeting V2.
 * @param {object} data - The meeting data to be created.
 * @returns {Promise<{message: string, data: {created: Array, failed: Array}, status_code: number, success: boolean}>}
 */
export const postMyMentorshipMeetingV2 = (data) =>
  request.post(API_ENDPOINTS.MENTORSHIP_MEETINGS_V2, data);
