/**
 * Auth0 sign-in providers and helpers for labeling and classifying them.
 *
 * A subject identifier has the shape `provider|id` (e.g. `google-oauth2|123`).
 * Both the Sign in & security page and its sign-in method list need the same
 * provider mapping, so it lives here once rather than being duplicated.
 */

/** The passwordless email-OTP provider. */
export const EMAIL_PROVIDER = "email";

/** Human-readable label per Auth0 provider prefix. */
export const PROVIDER_LABELS = {
  "google-oauth2": "Google",
  google: "Google",
  [EMAIL_PROVIDER]: "Email",
  auth0: "Email & password",
};

/**
 * The provider prefix of a `provider|id` subject identifier
 * (e.g. `"google-oauth2"`); empty string when absent.
 *
 * @param {string} subjectIdentifier
 * @returns {string}
 */
export const providerOf = (subjectIdentifier) =>
  (subjectIdentifier || "").split("|")[0];

/**
 * Human label for an identity's provider, parsed from the `provider|id`
 * prefix of its subject identifier.
 *
 * @param {string} subjectIdentifier
 * @returns {string}
 */
export const providerLabel = (subjectIdentifier) => {
  const provider = providerOf(subjectIdentifier);
  return PROVIDER_LABELS[provider] || provider || "Unknown";
};

/**
 * Whether a sign-in method authenticates by email (the passwordless email-OTP
 * provider). Only these methods expose contact-email management — the primary-
 * contact badge and the "Set as primary contact" action — because the contact
 * address is synced from the email method itself; SSO methods (e.g. Google) and
 * the email-and-password (auth0) method do not.
 *
 * @param {string} subjectIdentifier
 * @returns {boolean}
 */
export const isEmailMethod = (subjectIdentifier) =>
  providerOf(subjectIdentifier) === EMAIL_PROVIDER;

/**
 * Label for a whole identity in prose (e.g. confirmation dialogs): the provider
 * name, suffixed with its email claim when present. Falls back to a generic
 * phrase for an unknown provider so the sentence still reads naturally.
 *
 * @param {object} identity
 * @param {string} identity.subjectIdentifier
 * @param {string} [identity.emailClaim]
 * @returns {string}
 */
export const identityLabel = (identity) => {
  const provider = providerOf(identity.subjectIdentifier);
  const name = PROVIDER_LABELS[provider] || provider || "this sign-in method";
  return identity.emailClaim ? `${name} (${identity.emailClaim})` : name;
};
