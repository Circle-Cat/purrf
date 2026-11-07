import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * Fetches the signed-in user's progress on every onboarding guide they have
 * a record for. A guide with no row has never been seen.
 *
 * @returns {Promise<Array<{guideKey: string, status: string, snoozeCount: number, updatedAt: string}>>}
 *   The unwrapped `data` of the API envelope.
 */
export const listGuideProgress = async () =>
  (await request.get(API_ENDPOINTS.GUIDES_PROGRESS)).data;

/**
 * Records how the signed-in user ended one guide. The server owns the snooze
 * cap and never downgrades a completed or dismissed guide.
 *
 * @param {string} guideKey - The guide's key, e.g. "welcome".
 * @param {"completed"|"dismissed"|"snoozed"} status - How the guide ended.
 * @returns {Promise<{guideKey: string, status: string, snoozeCount: number, updatedAt: string}>}
 *   The stored row, unwrapped from the API envelope.
 */
export const recordGuideProgress = async (guideKey, status) =>
  (await request.put(API_ENDPOINTS.GUIDE_PROGRESS(guideKey), { status })).data;
