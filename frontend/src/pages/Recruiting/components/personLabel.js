/**
 * "User {id}", for a person with no action available to the viewer -- e.g.
 * a historical evaluator, whose evaluation already happened and can't be
 * undone.
 */
export const unresolvedPersonLabel = (id) => `User ${id}`;

/**
 * "User {id} — unavailable", for a person the viewer can remove (e.g. an
 * owner chip with its own remove button). Deliberately silent on why the id
 * didn't resolve: that reason (revoked permission, or a sanction only
 * account admins may see) isn't the viewer's to know.
 */
export const unavailablePersonLabel = (id) =>
  `${unresolvedPersonLabel(id)} — unavailable`;
