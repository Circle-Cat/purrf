import { Badge } from "@/components/ui/badge";
import TermHint from "@/pages/Recruiting/components/TermHint";
import { GLOSSARY, rejectTermId } from "@/pages/Recruiting/components/glossary";

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

const STATE_VARIANT = {
  draft: "secondary",
  published: "default",
  closed: "secondary",
};

/** Glossary id per base lifecycle stage. */
const BASE_TERM = {
  draft: "posting.draft",
  published: "posting.published",
  closed: "posting.closed",
};

/** Glossary id per pending sub-status; an absent JobStatus means no action badge. */
const ACTION_TERM = {
  pending_review: "posting.pending_review",
  published_pending_revision: "posting.revision_pending_review",
  pending_close: "posting.pending_close",
  pending_reopen: "posting.pending_reopen",
};

/**
 * State badge (Draft/Published/Closed), plus an optional action badge when a
 * review is currently pending, plus an optional reject-reason badge when the
 * posting's most recent review was a rejection. The rejection *comment* is
 * never revealed here; it lives in the dedicated panel on PostingDetailPage.
 * The action and reject badges are mutually exclusive by construction: a job's
 * reject info self-clears the instant a new review opens (becoming the "most
 * recent" review), and every pending sub-status corresponds to exactly one
 * open review. Shared between PostingsList and PostingDetailPage.
 *
 * Every label comes from the glossary, so a badge and its explanation cannot
 * disagree, and the flat seven-status legend that used to live in a help
 * dialog has no second copy to drift from.
 *
 * With ``explain`` each badge carries its own explanation, for the reader
 * looking at one posting and wondering what the pair of badges means. It is
 * opt-in because the list renders each row as a single click-through button,
 * and a focusable trigger inside that row would nest one control in another
 * and add a tab stop per posting.
 *
 * @param {{job: {status: string, lastRejectComment?: string,
 *          lastRejectKind?: string}, explain?: boolean}} props
 */
const PostingStatusBadges = ({ job, explain = false }) => {
  const baseTerm = BASE_TERM[BASE_STATE[job.status]];
  const actionTerm = ACTION_TERM[job.status];
  const rejectTerm = job.lastRejectComment
    ? rejectTermId(job.lastRejectKind)
    : null;

  /** The label alone, or the label with its hint attached. */
  const label = (id) => (explain ? <TermHint id={id} /> : GLOSSARY[id]?.label);

  return (
    <>
      <Badge variant={STATE_VARIANT[BASE_STATE[job.status]]}>
        {label(baseTerm)}
      </Badge>
      {actionTerm && <Badge variant="outline">{label(actionTerm)}</Badge>}
      {rejectTerm && <Badge variant="destructive">{label(rejectTerm)}</Badge>}
    </>
  );
};

export default PostingStatusBadges;
