/**
 * Humanize a snake_case stage/sub-status value for display, e.g.
 * "in_progress" -> "In progress", "recruiter_screening" -> "Recruiter screening".
 * Returns "" for null/undefined so callers can use it unconditionally.
 *
 * @param {string|null|undefined} value
 * @returns {string}
 */
export const humanize = (value) => {
  if (!value) return "";
  const spaced = value.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};
