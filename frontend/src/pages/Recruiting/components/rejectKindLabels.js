/**
 * Human label per `JobReviewKind` for a *rejected* review, shared by the
 * status badge (PostingStatusBadges) and the rejection-reason panel on the
 * posting detail page so the two can never drift apart.
 */
export const REJECT_KIND_LABEL = {
  initial: "Initial submission rejected",
  revision: "Revision rejected",
  close: "Close request rejected",
  reopen: "Reopen request rejected",
};

/**
 * Resolves a reject kind to its label, falling back for kinds this frontend
 * doesn't know yet (a backend-added JobReviewKind).
 *
 * @param {string | null | undefined} kind The `lastRejectKind` from JobDto.
 * @returns {string} The label to render.
 */
export const rejectKindLabel = (kind) => REJECT_KIND_LABEL[kind] ?? "Sent back";
