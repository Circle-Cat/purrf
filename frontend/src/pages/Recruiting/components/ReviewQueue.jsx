import { Button } from "@/components/ui/button";
import TermHint from "@/pages/Recruiting/components/TermHint";
import { reviewTermId } from "@/pages/Recruiting/components/glossary";
import { formatDateWithZone, resolveViewerTimezone } from "@/utils/dateTime";

/**
 * The reviewer's pending reviews, as a card on the postings page, laid out
 * like the mentorship console's pending-approvals card. Renders nothing when
 * there are none: a review leaves the queue as soon as it is decided, so an
 * empty card would only be noise above the postings list.
 *
 * Each row leads with its kind, which carries what approving and rejecting
 * that kind actually do, and those differ sharply -- rejecting an initial
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
  const timezone = resolveViewerTimezone();
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <header className="flex items-center gap-3 border-b border-slate-200 px-5 py-3">
        <h2 className="text-sm font-semibold">Pending approvals</h2>
        <span className="ml-auto text-xs text-slate-500">
          {reviews.length} waiting
        </span>
      </header>
      <ul className="divide-y divide-slate-200 px-5">
        {reviews.map((r) => {
          const termId = reviewTermId(r.kind);
          const submitted = formatDateWithZone(r.createdAt, timezone);
          return (
            <li key={r.reviewId} className="flex flex-wrap gap-3 py-3">
              <div className="min-w-64 flex-1">
                <p className="text-sm font-medium">
                  {termId ? <TermHint id={termId} /> : <span>{r.kind}</span>} —{" "}
                  <span>{r.jobTitle || `Job #${r.jobId}`}</span>
                </p>
                {r.submitMessage && (
                  <p className="mt-1 text-sm text-slate-600">
                    {r.submitMessage}
                  </p>
                )}
                <p className="mt-1 text-xs text-slate-500">
                  {submitted && <>Submitted {submitted} · </>}Sent to{" "}
                  <strong>you</strong>
                </p>
              </div>
              <div className="self-center">
                <Button size="sm" onClick={() => onOpen(r)}>
                  Review
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
};

export default ReviewQueue;
