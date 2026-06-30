/**
 * Resolve the name to show for a mentorship partner (someone other than the
 * viewer). The preferred name takes priority; when it is missing the full
 * "first last" name is used as a fallback. This mirrors the backend
 * `partner_display_name` helper so partner-facing surfaces stay consistent.
 *
 * Note: this is only for viewing *other* people. When a user views their own
 * name, or in admin/audit views, render firstName, lastName and preferredName
 * separately instead.
 *
 * @param {{firstName?: string, lastName?: string, preferredName?: string}} [person]
 *   The partner whose name should be displayed.
 * @returns {string} The preferred name, or the trimmed "first last" fallback;
 *   an empty string when nothing usable is provided.
 */
export function partnerDisplayName(person) {
  if (!person) return "";

  const preferred = person.preferredName?.trim();
  if (preferred) return preferred;

  return `${person.firstName ?? ""} ${person.lastName ?? ""}`.trim();
}
