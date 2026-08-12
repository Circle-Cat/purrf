import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import EmptyState from "@/pages/Recruiting/components/EmptyState";
import TermHint from "@/pages/Recruiting/components/TermHint";
import { GLOSSARY } from "@/pages/Recruiting/components/glossary";

/**
 * Resolves a JobReviewKind to its glossary id, or null for a kind this
 * frontend does not know yet (a backend-added JobReviewKind), which falls
 * back to showing the raw kind rather than nothing.
 *
 * @param {string} kind A JobReviewKind value.
 * @returns {string|null}
 */
const reviewTermId = (kind) =>
  GLOSSARY[`review.${kind}`] ? `review.${kind}` : null;

/**
 * The reviewer's pending reviews. Each row's kind badge carries what
 * approving and rejecting that kind actually do, which differs sharply
 * between them -- rejecting an initial request sends a posting back to Draft,
 * while rejecting a close request changes nothing at all.
 *
 * A row is not itself clickable (it holds its own Review button), so a
 * tooltip trigger inside it nests nothing.
 *
 * @param {{reviews: object[], onOpen: Function}} props
 */
const ReviewQueue = ({ reviews, onOpen }) => (
  <div className="space-y-4">
    {reviews.length === 0 ? (
      <EmptyState
        what="Postings submitted for your approval appear here."
        how="An author picks you as the reviewer when they submit a posting."
        who="You can't add one yourself, and you can't review your own postings."
      />
    ) : (
      <div className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
        {reviews.map((r) => {
          const termId = reviewTermId(r.kind);
          return (
            <div key={r.reviewId} className="flex items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-900">
                  {r.jobTitle || `Job #${r.jobId}`}
                </p>
                {r.submitMessage && (
                  <p className="truncate text-xs text-slate-500">
                    {r.submitMessage}
                  </p>
                )}
              </div>
              <Badge variant="outline">
                {termId ? <TermHint id={termId} /> : r.kind}
              </Badge>
              <Button size="sm" onClick={() => onOpen(r)}>
                Review
              </Button>
            </div>
          );
        })}
      </div>
    )}
  </div>
);

export default ReviewQueue;
