import { useState } from "react";
import { Button } from "@/components/ui/button";
import ApprovalDecisionDialog from "@/components/approval/ApprovalDecisionDialog";
import {
  formatDateTimeWithZone,
  resolveViewerTimezone,
} from "@/utils/dateTime";

/** "recruiting_application" reads as "recruiting application" outside that domain. */
const humanizeSource = (raisedFrom) =>
  (raisedFrom ?? "").replace(/_/g, " ").trim();

/**
 * The block request waiting on this viewer's decision, shown on the account it
 * is about. Rendered only when a pending request names the viewer as its
 * reviewer -- a request is nobody else's to see, which the endpoint enforces.
 *
 * Both decisions are confirmed in the shared decision dialog: approving blocks
 * at once, and rejecting asks for the reason the raiser is emailed.
 *
 * @param {Object} props
 * @param {Object} props.request - BlockRequestDto for this account.
 * @param {(note: string|null) => void} props.onApprove - Approve and block.
 * @param {(note: string) => void} props.onReject - Turn the request down,
 *   with the reason.
 * @param {boolean} props.submitting - A decision is in flight.
 */
const BlockRequestCard = ({ request, onApprove, onReject, submitting }) => {
  const tz = resolveViewerTimezone();
  const [decision, setDecision] = useState(null);
  const source = humanizeSource(request.raisedFrom);
  const target = request.targetName || "this person";

  return (
    <section className="rounded-lg border border-amber-300 bg-amber-50 p-4">
      <h2 className="text-sm font-bold uppercase tracking-wide text-amber-900">
        Block request awaiting your decision
      </h2>
      <p className="mt-1 text-sm text-amber-900">
        Raised by {request.raisedByName}
        {source ? ` from ${source}` : ""} on{" "}
        {formatDateTimeWithZone(request.raisedAt, tz)}
      </p>
      {request.reason ? (
        <p className="mt-3 whitespace-pre-wrap text-sm text-slate-900">
          {request.reason}
        </p>
      ) : (
        <p className="mt-3 text-sm text-slate-500">No reason given.</p>
      )}
      <div className="mt-4 flex gap-2">
        <Button
          type="button"
          variant="destructive"
          onClick={() => setDecision("approve")}
          disabled={submitting}
        >
          Approve and block
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => setDecision("reject")}
          disabled={submitting}
        >
          Reject
        </Button>
      </div>
      <ApprovalDecisionDialog
        open={decision !== null}
        onOpenChange={(open) => !open && setDecision(null)}
        decision={decision ?? "approve"}
        title={
          decision === "reject"
            ? "Reject this block request"
            : `Block ${target}?`
        }
        description={
          decision === "reject"
            ? `${target} is not blocked. ${request.raisedByName || "The raiser"} is told your reason.`
            : `${target} is blocked from Purrf at once: their open applications close and their upcoming interviews are cancelled.`
        }
        onConfirm={(comment) => {
          if (decision === "reject") onReject(comment);
          else onApprove(null);
          setDecision(null);
        }}
        submitting={submitting}
      />
    </section>
  );
};

export default BlockRequestCard;
