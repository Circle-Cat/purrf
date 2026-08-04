import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/** Human labels per JobReviewKind, matching the "How it works" guide's status legend. */
const KIND_LABELS = {
  initial: "Initial Request",
  revision: "Revision Request",
  close: "Close Request",
  reopen: "Reopen Request",
};

/**
 * Read-only list of the reviewer's pending reviews.
 *
 * @param {{reviews: object[], onOpen: Function}} props
 */
const ReviewQueue = ({ reviews, onOpen }) => (
  <div className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
    {reviews.length === 0 && (
      <p className="p-6 text-sm text-slate-500">No pending reviews.</p>
    )}
    {reviews.map((r) => (
      <div key={r.reviewId} className="flex items-center gap-3 p-4">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-slate-900">
            {r.jobTitle || `Job #${r.jobId}`}
          </p>
          {r.submitMessage && (
            <p className="truncate text-xs text-slate-500">{r.submitMessage}</p>
          )}
        </div>
        <Badge variant="outline">{KIND_LABELS[r.kind] ?? r.kind}</Badge>
        <Button size="sm" onClick={() => onOpen(r)}>
          Review
        </Button>
      </div>
    ))}
  </div>
);

export default ReviewQueue;
