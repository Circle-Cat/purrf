import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
 * @param {Object} props
 * @param {Object} props.request - BlockRequestDto for this account.
 * @param {(note: string|null) => void} props.onApprove - Approve and block.
 * @param {(note: string|null) => void} props.onReject - Turn the request down.
 * @param {boolean} props.submitting - A decision is in flight.
 */
const BlockRequestCard = ({ request, onApprove, onReject, submitting }) => {
  const tz = resolveViewerTimezone();
  const [note, setNote] = useState("");
  // The raiser is told the outcome by email, and that email renders this note
  // when there is one. Without somewhere to type it, a rejection reaches them
  // as a bare no.
  const decisionNote = () => note.trim() || null;
  const source = humanizeSource(request.raisedFrom);

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
      <p className="mt-3 whitespace-pre-wrap text-sm text-slate-900">
        {request.reason}
      </p>
      <div className="mt-4 space-y-1">
        <Label htmlFor="decision-note">
          Note — optional, sent to the raiser
        </Label>
        <Textarea
          id="decision-note"
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <div className="mt-4 flex gap-2">
        <Button
          type="button"
          variant="destructive"
          onClick={() => onApprove(decisionNote())}
          disabled={submitting}
        >
          Approve and block
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => onReject(decisionNote())}
          disabled={submitting}
        >
          Reject
        </Button>
      </div>
    </section>
  );
};

export default BlockRequestCard;
