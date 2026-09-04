/**
 * Resolve the name to show for someone other than the viewer. The preferred
 * name takes priority; when it is missing the full "first last" name is used
 * as a fallback. This mirrors the backend `user_display_name` helper so every
 * surface that names another person stays consistent.
 *
 * Note: this is only for viewing *other* people. When a user views their own
 * name, or in admin/audit views, render firstName, lastName and preferredName
 * separately instead. Recruiting candidates are named by their legal
 * "first last" name and are resolved on the backend, not here.
 *
 * @param {{firstName?: string, lastName?: string, preferredName?: string}} [person]
 *   The person whose name should be displayed.
 * @returns {string} The preferred name, or the trimmed "first last" fallback;
 *   an empty string when nothing usable is provided.
 */
export function userDisplayName(person) {
  if (!person) return "";

  const preferred = person.preferredName?.trim();
  if (preferred) return preferred;

  return `${person.firstName ?? ""} ${person.lastName ?? ""}`.trim();
}

/**
 * Render a person's legal name for a place that has room for one cell only.
 *
 * Admin and audit views show `firstName`, `lastName` and `preferredName`
 * separately and verbatim, which is what the wide tables do. A single cell —
 * the "By" column of an audit row, say — cannot hold three fields, so it falls
 * back to the legal name and drops the preferred one.
 *
 * Dropping the preferred name loses a nickname. *Substituting* it, the way
 * `userDisplayName` does, loses the identity the view exists to confirm — so
 * that is the one thing a cell like this must never do.
 *
 * @param {{firstName?: string, lastName?: string}} [person]
 * @returns {string} Empty string when nothing usable is provided.
 */
export function legalName(person) {
  if (!person) return "";
  return `${person.firstName ?? ""} ${person.lastName ?? ""}`.trim();
}
