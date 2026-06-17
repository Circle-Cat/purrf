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
 *   internalIdentity: { identityId: number, subjectIdentifier: string,
 *     emailClaim: string|null, linkedAt: string|null, lastUsedAt: string|null }|null,
 *   externalIdentities: Array<object>,
 * } }>}
 */
export async function listEmails() {
  return await request.get(API_ENDPOINTS.EMAIL_LIST);
}
