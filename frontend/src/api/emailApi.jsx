import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * Start email OTP verification: asks the backend to send a one-time code to
 * `email` and returns a signed state token to submit alongside the code.
 *
 * @param {string} email
 * @returns {Promise<{ data: { state: string } }>}
 */
export async function initiateEmailVerification(email) {
  return await request.post(API_ENDPOINTS.EMAIL_OTP_INITIATE, { email });
}

/**
 * Confirm the OTP for a previously initiated verification.
 *
 * @param {string} state - token returned by initiateEmailVerification
 * @param {string} otp - the 6-digit code the user received
 * @returns {Promise<{ data: { ok: boolean, linked_sub: string, email: string } }>}
 */
export async function verifyEmailOtp(state, otp) {
  return await request.post(API_ENDPOINTS.EMAIL_OTP_VERIFY, { state, otp });
}

/**
 * Fetch the caller's comprehensive email + sign-in identity view that backs
 * the Sign in & security settings page.
 *
 * @returns {Promise<{ data: {
 *   emails: Array<{ emailId: number, email: string, otpConfirmed: boolean,
 *     isPrimary: boolean, addedAt: string, linkedIdentityCount: number }>,
 *   internalIdentities: Array<object>,
 *   externalIdentities: Array<object>,
 * } }>}
 */
export async function listEmails() {
  return await request.get(API_ENDPOINTS.EMAIL_LIST);
}

/**
 * Begin a step-up switch of the primary contact email: the backend sends an
 * OTP to the current primary and returns a signed state.
 *
 * @param {number} emailId
 * @returns {Promise<{ data: { state: string } }>}
 */
export async function initiateSetPrimary(emailId) {
  return await request.post(API_ENDPOINTS.EMAIL_SET_PRIMARY_INITIATE(emailId));
}

/**
 * Confirm a step-up primary switch with the OTP sent to the current primary.
 *
 * @param {number} emailId
 * @param {string} state - token from initiateSetPrimary
 * @param {string} code - the 6-digit code the user received
 * @returns {Promise<{ data: { ok: boolean } }>}
 */
export async function confirmSetPrimary(emailId, state, code) {
  return await request.post(API_ENDPOINTS.EMAIL_SET_PRIMARY_CONFIRM(emailId), {
    state,
    code,
  });
}

/**
 * Begin a step-up unlink of one of the caller's sign-in identities: the backend
 * sends an OTP to the current primary and returns a signed state. Unlinking
 * also drops the identity's synced contact email when nothing else uses it.
 *
 * @param {number} identityId
 * @returns {Promise<{ data: { state: string } }>}
 */
export async function initiateUnlink(identityId) {
  return await request.post(API_ENDPOINTS.EMAIL_UNLINK_INITIATE(identityId));
}

/**
 * Confirm a step-up unlink with the OTP sent to the primary address.
 *
 * @param {number} identityId
 * @param {string} state - token from initiateUnlink
 * @param {string} code - the 6-digit code the user received
 * @returns {Promise<{ data: { ok: boolean } }>}
 */
export async function confirmUnlink(identityId, state, code) {
  return await request.post(API_ENDPOINTS.EMAIL_UNLINK_CONFIRM(identityId), {
    state,
    code,
  });
}
