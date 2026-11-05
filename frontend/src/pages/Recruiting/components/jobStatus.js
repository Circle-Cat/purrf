/**
 * How a posting's status decides what the page shows. Three maps that must
 * between them account for every `JobStatus`, kept in one module so a single
 * test can prove they do -- a status that falls through every one of them
 * renders a blank badge, or a notice that says a posting is locked without
 * saying what it is waiting for.
 *
 * Held to the backend enum by `tests/shared/job_statuses.json`.
 */

/** Every `JobStatus`, mirroring `backend/common/recruiting_enums.py`. */
export const JOB_STATUSES = [
  "draft",
  "pending_review",
  "published",
  "closed",
  "published_pending_revision",
  "pending_close",
  "pending_reopen",
];

/**
 * The statuses that still have an author action available, and so render the
 * `Operate:` row. Their complement renders a `PendingNotice` instead.
 */
export const OPERABLE_STATUSES = ["draft", "published", "closed"];

/**
 * What the posting is waiting on, per status with no Operate action left.
 * Naming the specific request matters: three of these four are not a
 * submission for publication, and calling them one would be wrong.
 */
export const PENDING_HEADLINE = {
  pending_review: "Submitted for review",
  published_pending_revision: "Revision submitted for review",
  pending_close: "Close requested",
  pending_reopen: "Reopen requested",
};

/**
 * Glossary id per status, for the base badge. Keyed by status rather than by
 * base state because `draft` and `pending_review` share the `Draft` badge but
 * need opposite explanations -- one is freely editable, the other is frozen --
 * so a single term keyed on the shared base state is wrong for whichever case
 * it was not written for.
 */
export const BASE_TERM = {
  draft: "posting.draft",
  pending_review: "posting.draft_in_review",
  published: "posting.published",
  published_pending_revision: "posting.published",
  pending_close: "posting.published",
  pending_reopen: "posting.closed",
  closed: "posting.closed",
};

/** Glossary id per pending status, for the action badge beside the base one. */
export const ACTION_TERM = {
  pending_review: "posting.pending_review",
  published_pending_revision: "posting.revision_pending_review",
  pending_close: "posting.pending_close",
  pending_reopen: "posting.pending_reopen",
};

/** Maps every JobStatus to its 3-state base lifecycle stage. */
export const BASE_STATE = {
  draft: "draft",
  pending_review: "draft",
  published: "published",
  published_pending_revision: "published",
  pending_close: "published",
  pending_reopen: "closed",
  closed: "closed",
};
