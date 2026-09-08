/**
 * The reviewers a block request may legally name.
 *
 * Mirrors `_validate_reviewer` on the backend, which refuses a reviewer who is
 * the raiser, the person the request is about, or -- when reassigning -- the
 * reviewer who already holds it. Kept in one place so the next exclusion the
 * backend grows is added once rather than found in two dialogs.
 *
 * @param {{userId: number, name: string}[]} holders Active reviewers.
 * @param {(number|null|undefined)[]} excluded Ids that may not be picked.
 * @returns {{userId: number, name: string}[]} What the picker may offer.
 */
export function pickableReviewers(holders, excluded) {
  const blocked = new Set(excluded.filter((id) => id != null));
  return (holders ?? []).filter((h) => !blocked.has(h.userId));
}
