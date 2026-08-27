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
