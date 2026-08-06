import { Badge } from "@/components/ui/badge";
import { rejectKindLabel } from "@/pages/Recruiting/components/rejectKindLabels";

/** Maps every JobStatus to its 3-state base lifecycle stage. */
const BASE_STATE = {
  draft: "draft",
  pending_review: "draft",
  published: "published",
  published_pending_revision: "published",
  pending_close: "published",
  pending_reopen: "closed",
  closed: "closed",
};

/** Human label + badge variant per base lifecycle stage. */
const STATE_LABELS = {
  draft: "Draft",
  published: "Published",
  closed: "Closed",
};

const STATE_VARIANT = {
  draft: "secondary",
  published: "default",
  closed: "secondary",
};

/** Action-badge label per pending sub-status; absent JobStatus keys mean no action badge. */
const ACTION_LABELS = {
  pending_review: "Pending review",
  published_pending_revision: "Revision pending review",
  pending_close: "Pending close",
  pending_reopen: "Pending reopen",
};

/**
 * State badge (Draft/Published/Closed), plus an optional action badge when
 * a review is currently pending, plus an optional reject-reason badge when
 * the posting's most recent review was a rejection. Every badge is plain,
 * non-interactive text: the rejection *comment* is not revealed here at all,
 * it lives in the dedicated panel on PostingDetailPage.
 * The action and reject badges are mutually exclusive by construction: a
 * job's reject info self-clears the instant a new review opens (becoming
 * the "most recent" review), and every pending sub-status corresponds to
 * exactly one open review. Shared between PostingsList and PostingDetailPage.
 *
 * @param {{job: {status: string, lastRejectComment?: string,
 *          lastRejectKind?: string}}} props
 */
const PostingStatusBadges = ({ job }) => {
  const baseState = BASE_STATE[job.status];
  const actionLabel = ACTION_LABELS[job.status];

  return (
    <>
      <Badge variant={STATE_VARIANT[baseState]}>
        {STATE_LABELS[baseState]}
      </Badge>
      {actionLabel && <Badge variant="outline">{actionLabel}</Badge>}
      {job.lastRejectComment && (
        <Badge variant="destructive">
          {rejectKindLabel(job.lastRejectKind)}
        </Badge>
      )}
    </>
  );
};

export default PostingStatusBadges;
