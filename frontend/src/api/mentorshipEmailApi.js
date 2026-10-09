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
 * Lists, per person, the stages they were actually notified of in a round.
 *
 * @param {number|string} roundId - The mentorship round's id.
 * @returns {Promise<Array<{userId: number, stages: string[]}>>}
 */
export const listNotifiedStages = async (roundId) =>
  (
    await request.get(API_ENDPOINTS.MENTORSHIP_ADMIN_EMAIL_SENDS_NOTIFIED, {
      params: { roundId },
    })
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
