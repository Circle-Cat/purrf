import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import TermHint from "@/pages/Recruiting/components/TermHint";
import { reviewTermId } from "@/pages/Recruiting/components/glossary";

/**
 * The reviewer's pending reviews, as a card on the postings page. Renders
 * nothing when there are none: a review leaves the queue as soon as it is
 * decided, so an empty card would only be noise above the postings list.
 *
 * Each row's kind badge carries what approving and rejecting that kind
 * actually do, which differs sharply between them -- rejecting an initial
 * request sends a posting back to Draft, while rejecting a close request
 * changes nothing at all.
 *
 * A row is not itself clickable (it holds its own Review button), so a
 * tooltip trigger inside it nests nothing.
 *
 * @param {{reviews: object[], onOpen: Function}} props
 */
const ReviewQueue = ({ reviews, onOpen }) => {
  if (reviews.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          Waiting for your review ({reviews.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="divide-y divide-slate-200">
        {reviews.map((r) => {
          const termId = reviewTermId(r.kind);
          return (
            <div
              key={r.reviewId}
              className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
            >
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
      </CardContent>
    </Card>
  );
};

export default ReviewQueue;
