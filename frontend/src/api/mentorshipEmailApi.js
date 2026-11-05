import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

// Calls that wait on Kit can exceed the default 10 s axios timeout.
const KIT = { timeout: 60000 };

/**
 * Lists the broadcast drafts in Kit that a notification can be made from.
 *
 * @returns {Promise<Array<{id: number, subject: string, createdAt: string, problem: (string|null)}>>} `problem` says why a draft cannot be sent.
 */
export const listKitDrafts = async () =>
  (await request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_KIT_DRAFTS, KIT)).data;

/**
 * Creates a notification send for some of a round's people from a Kit draft.
 *
 * @param {{roundId: number, stage: string, kitDraftId: number, userIds: number[]}} body
 * @returns {Promise<Object>} The new send.
 */
export const createEmailSend = async (body) =>
  (await request.post(API_ENDPOINTS.MENTORSHIP_ADMIN_EMAIL_SENDS, body, KIT))
    .data;

/**
 * Lists, per person, the stages they were actually notified of in a round,
 * and per stage the latest send confirmed for them and still to go out.
 *
 * @param {number|string} roundId - The mentorship round's id.
 * @returns {Promise<Array<{
 *   userId: number,
 *   stages: string[],
 *   scheduled: Array<{stage: string, sendAt: string}>,
 * }>>}
 */
export const listNotifiedStages = async (roundId) =>
  (
    await request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_EMAIL_SENDS_NOTIFIED, {
      params: { roundId },
    })
  ).data;

/**
 * Lists one person's sends in a round that have played out, newest first:
 * sent to them, or not, with why. Ones still to go out are not included.
 *
 * @param {number|string} roundId - The mentorship round's id.
 * @param {number|string} userId - The person's user id.
 * @returns {Promise<Array<{
 *   sendId: number,
 *   stage: string,
 *   subject: string,
 *   delivered: boolean,
 *   reason: string|null,
 *   at: string,
 * }>>}
 */
export const listPersonSends = async (roundId, userId) =>
  (
    await request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_EMAIL_SENDS_PERSON, {
      params: { roundId, userId },
    })
  ).data;

/**
 * Records that a notification reached people some other way -- Teams,
 * Google Chat, a call. People already notified of the stage, or not offered
 * it, are skipped and listed with why.
 *
 * @param {number|string} roundId - The mentorship round's id.
 * @param {{userIds: number[], stage: string, body: string}} body - Who, which
 *   notification, and how it was sent.
 * @returns {Promise<{marked: number[], skipped: Array<{userId: number, reason: string}>}>}
 */
export const markNotified = async (roundId, body) =>
  (
    await request.post(
      API_ENDPOINTS.MENTORSHIP_ADMIN_NOTIFICATIONS_MARK(roundId),
      body,
    )
  ).data;

const action = async (sendId, name, body) =>
  (
    await request.post(
      API_ENDPOINTS.MENTORSHIP_ADMIN_EMAIL_SEND_ACTION(sendId, name),
      body,
      KIT,
    )
  ).data;

/**
 * Renders the send's email as it will go out, with the checks to pass first.
 *
 * @param {number} sendId
 * @returns {Promise<Object>} The preview, carrying the token Confirm needs.
 */
export const refreshEmailPreview = (sendId) =>
  action(sendId, "preview", undefined);

/**
 * Schedules the send for the previewed email.
 *
 * @param {number} sendId
 * @param {{sendAt: string, previewToken: string}} body - sendAt in UTC ISO.
 * @returns {Promise<Object>}
 */
export const confirmEmailSend = (sendId, body) =>
  action(sendId, "confirm", body);

/**
 * Cancels a send that has not gone out.
 *
 * @param {number} sendId
 * @returns {Promise<Object>}
 */
export const cancelEmailSend = (sendId) => action(sendId, "cancel", undefined);
