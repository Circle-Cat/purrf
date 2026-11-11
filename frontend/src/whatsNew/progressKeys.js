// Progress keys share the onboarding guides' table, whose keys are 1 to 64
// lowercase letters, digits or hyphens. Entry ids are at most 50 characters
// and may not be "intro", so no entry key collides with the intro's.

/** Progress key of the one-time pointer at the avatar. */
export const WHATS_NEW_INTRO_KEY = "whats-new-intro";

/**
 * Progress key holding one viewer's read state for one entry.
 *
 * @param {string} entryId - The entry's `id`.
 * @returns {string} e.g. "whats-new-sign-in-with-any-email".
 */
export const whatsNewEntryKey = (entryId) => `whats-new-${entryId}`;
